"""结晶调度器.

定时任务调度器，负责在指定时间窗口执行结晶任务。

功能追溯ID: F-MEM-005
"""

import random
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any, Dict, List, Optional

from src.domain.memory.crystallization.conditions import CrystallizationConditions
from src.domain.memory.crystallization.executor import CrystallizationExecutor
from src.domain.memory.meta_memory import CrystallizationResult
from src.domain.models.base import now_timestamp
from src.infrastructure.db.cognitive_gap import CognitiveGap
from src.infrastructure.db.enums import GapStatus
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SchedulerConfig:
    """调度器配置."""
    
    # 执行时间窗口 (默认凌晨2-4点)
    start_hour: int = 2
    start_minute: int = 0
    end_hour: int = 4
    end_minute: int = 0
    
    # 批次设置
    batch_size: int = 100  # 每批处理数量
    batch_interval_seconds: int = 30  # 批次间隔
    
    # 重试设置
    max_retries: int = 3
    retry_interval_seconds: int = 300
    
    # 执行模式
    dry_run: bool = False  # 是否只模拟不执行
    force_crystallization: bool = False  # 是否强制结晶


@dataclass
class SchedulerRunResult:
    """调度器运行结果."""
    
    run_id: str
    started_at: datetime
    completed_at: datetime
    total_gaps: int
    crystallized: int
    dismissed: int
    failed: int
    skipped: int
    details: List[CrystallizationResult]
    
    @property
    def success_rate(self) -> float:
        """成功率."""
        if self.total_gaps == 0:
            return 0.0
        return (self.crystallized + self.dismissed) / self.total_gaps
    
    @property
    def duration_seconds(self) -> float:
        """执行时长."""
        return (self.completed_at - self.started_at).total_seconds()


class CrystallizationScheduler:
    """结晶调度器.
    
    定时任务调度器:
    - 每天凌晨2-4点执行结晶任务
    - 查询所有pending状态的认知缺口
    - 检查结晶条件
    - 执行状态流转
    """
    
    def __init__(
        self,
        gap_repo,
        evidence_repo,
        executor: Optional[CrystallizationExecutor] = None,
        conditions: Optional[CrystallizationConditions] = None,
        config: Optional[SchedulerConfig] = None,
    ):
        """初始化调度器.
        
        Args:
            gap_repo: 认知缺口Repository
            evidence_repo: 证据Repository
            executor: 结晶执行器(可选)
            conditions: 条件判定器(可选)
            config: 调度配置(可选)
        """
        self._gap_repo = gap_repo
        self._evidence_repo = evidence_repo
        self._executor = executor
        self._conditions = conditions or CrystallizationConditions()
        self._config = config or SchedulerConfig()
    
    async def run_daily_crystallization(
        self,
        student_id: Optional[str] = None,
    ) -> SchedulerRunResult:
        """执行每日结晶任务.
        
        Args:
            student_id: 学生ID(可选，None则处理所有)
            
        Returns:
            运行结果
        """
        run_id = f"run_{now_timestamp().strftime('%Y%m%d_%H%M%S')}"
        started_at = now_timestamp()
        
        logger.info(
            f"Starting daily crystallization: run_id={run_id}, "
            f"student_id={student_id or 'all'}"
        )
        
        try:
            # 1. 查询所有待处理缺口
            pending_gaps = await self._get_pending_gaps(student_id)
            logger.info(f"Found {len(pending_gaps)} pending gaps")
            
            if not pending_gaps:
                return SchedulerRunResult(
                    run_id=run_id,
                    started_at=started_at,
                    completed_at=now_timestamp(),
                    total_gaps=0,
                    crystallized=0,
                    dismissed=0,
                    failed=0,
                    skipped=0,
                    details=[],
                )
            
            # 2. 按优先级排序
            sorted_gaps = self._sort_by_priority(pending_gaps)
            
            # 3. 批量处理
            results = await self._process_gaps(sorted_gaps)
            
            # 4. 统计结果
            completed_at = now_timestamp()
            
            stats = self._calculate_stats(results)
            
            run_result = SchedulerRunResult(
                run_id=run_id,
                started_at=started_at,
                completed_at=completed_at,
                total_gaps=len(pending_gaps),
                crystallized=stats["crystallized"],
                dismissed=stats["dismissed"],
                failed=stats["failed"],
                skipped=stats["skipped"],
                details=results,
            )
            
            logger.info(
                f"Daily crystallization completed: "
                f"total={run_result.total_gaps}, "
                f"crystallized={run_result.crystallized}, "
                f"dismissed={run_result.dismissed}, "
                f"success_rate={run_result.success_rate:.2%}"
            )
            
            return run_result
            
        except Exception as e:
            logger.error(f"Daily crystallization failed: {e}")
            raise
    
    async def run_immediate_crystallization(
        self,
        gap_id: str,
        force: bool = False,
    ) -> Optional[CrystallizationResult]:
        """立即执行单个缺口结晶.
        
        Args:
            gap_id: 缺口ID
            force: 是否强制结晶
            
        Returns:
            结晶结果
        """
        logger.info(f"Running immediate crystallization for gap {gap_id}")
        
        if not self._executor:
            # 延迟初始化executor
            self._executor = CrystallizationExecutor(
                self._gap_repo,
                self._evidence_repo,
            )
        
        return await self._executor.crystallize(gap_id, force=force)
    
    def is_in_execution_window(self, current_time: Optional[datetime] = None) -> bool:
        """检查当前是否在执行窗口内.
        
        Args:
            current_time: 当前时间(默认now)
            
        Returns:
            是否在窗口内
        """
        current = current_time or now_timestamp()
        current_time_only = current.time()
        
        start_time = time(self._config.start_hour, self._config.start_minute)
        end_time = time(self._config.end_hour, self._config.end_minute)
        
        # 处理跨午夜的情况
        if start_time <= end_time:
            return start_time <= current_time_only <= end_time
        else:
            return current_time_only >= start_time or current_time_only <= end_time
    
    def get_next_run_time(self, from_time: Optional[datetime] = None) -> datetime:
        """获取下次运行时间.
        
        Args:
            from_time: 基准时间(默认now)
            
        Returns:
            下次运行时间
        """
        base = from_time or now_timestamp()
        
        # 今天的执行时间
        next_run = base.replace(
            hour=self._config.start_hour,
            minute=self._config.start_minute,
            second=0,
            microsecond=0,
        )
        
        # 如果今天的时间已过，设置为明天
        if next_run <= base:
            next_run += timedelta(days=1)
        
        # 添加随机偏移(0-30分钟)以避免所有实例同时执行
        jitter = random.randint(0, 30)
        next_run += timedelta(minutes=jitter)
        
        return next_run
    
    async def _get_pending_gaps(
        self,
        student_id: Optional[str] = None,
    ) -> List[CognitiveGap]:
        """获取待处理缺口.
        
        Args:
            student_id: 学生ID(可选)
            
        Returns:
            待处理缺口列表
        """
        filters = {"status": GapStatus.PENDING.value}
        if student_id:
            filters["student_id"] = student_id
        
        gaps = await self._gap_repo.find_many(**filters)
        return list(gaps)
    
    def _sort_by_priority(
        self,
        gaps: List[CognitiveGap],
    ) -> List[CognitiveGap]:
        """按优先级排序.
        
        优先级规则:
        1. 观察期已结束的优先
        2. 出现次数多的优先
        3. 时间久的优先
        
        Args:
            gaps: 缺口列表
            
        Returns:
            排序后的列表
        """
        def priority_score(gap: CognitiveGap) -> int:
            score = 0
            
            # 观察期结束的优先
            cutoff_time = gap.discovered_at + timedelta(
                hours=self._conditions.observation_period_hours
            )
            if now_timestamp() >= cutoff_time:
                score += 1000
            
            # 出现次数
            score += gap.occurrence_count * 100
            
            # 等待天数
            days_pending = (now_timestamp() - gap.discovered_at).days
            score += days_pending * 10
            
            return score
        
        return sorted(gaps, key=priority_score, reverse=True)
    
    async def _process_gaps(
        self,
        gaps: List[CognitiveGap],
    ) -> List[CrystallizationResult]:
        """处理缺口列表.
        
        Args:
            gaps: 缺口列表
            
        Returns:
            处理结果列表
        """
        if not self._executor:
            self._executor = CrystallizationExecutor(
                self._gap_repo,
                self._evidence_repo,
            )
        
        results = []
        batch_size = self._config.batch_size
        
        for i in range(0, len(gaps), batch_size):
            batch = gaps[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: {len(batch)} gaps")
            
            for gap in batch:
                result = await self._process_single_gap(gap)
                if result:
                    results.append(result)
            
            # 批次间隔
            if i + batch_size < len(gaps):
                import asyncio
                await asyncio.sleep(self._config.batch_interval_seconds)
        
        return results
    
    async def _process_single_gap(
        self,
        gap: CognitiveGap,
    ) -> Optional[CrystallizationResult]:
        """处理单个缺口.
        
        Args:
            gap: 认知缺口
            
        Returns:
            处理结果
        """
        try:
            # 获取证据
            evidences = await self._evidence_repo.find_many(gap_id=gap.gap_id)
            evidence_types = [e.evidence_type for e in evidences]
            
            # 检查条件
            check_result = self._conditions.check_crystallization(
                gap,
                evidence_types,
            )
            
            if self._config.dry_run:
                # 仅模拟，不执行
                return CrystallizationResult(
                    gap_id=gap.gap_id,
                    student_id=gap.student_id,
                    success=True,
                    new_status=GapStatus.CRYSTALLIZED.value if check_result.can_crystallize else GapStatus.PENDING.value,
                    reason=f"[DRY RUN] {check_result.reason}",
                )
            
            if check_result.can_crystallize:
                # 执行结晶
                return await self._executor.crystallize(
                    gap.gap_id,
                    force=self._config.force_crystallization,
                )
            else:
                # 检查是否应该排除
                if "should dismiss" in check_result.reason.lower():
                    return await self._executor.dismiss(
                        gap.gap_id,
                        reason="No evidence during observation period",
                    )
                
                # 继续观察
                return CrystallizationResult(
                    gap_id=gap.gap_id,
                    student_id=gap.student_id,
                    success=False,
                    new_status=GapStatus.PENDING.value,
                    reason=check_result.reason,
                )
                
        except Exception as e:
            logger.error(f"Failed to process gap {gap.gap_id}: {e}")
            return CrystallizationResult(
                gap_id=gap.gap_id,
                student_id=gap.student_id,
                success=False,
                new_status=GapStatus.PENDING.value,
                reason=f"Processing error: {str(e)}",
            )
    
    def _calculate_stats(
        self,
        results: List[CrystallizationResult],
    ) -> Dict[str, int]:
        """计算统计信息.
        
        Args:
            results: 结果列表
            
        Returns:
            统计字典
        """
        stats = {
            "crystallized": 0,
            "dismissed": 0,
            "failed": 0,
            "skipped": 0,
        }
        
        for r in results:
            if r.success:
                if r.new_status == GapStatus.CRYSTALLIZED.value:
                    stats["crystallized"] += 1
                elif r.new_status == GapStatus.DISMISSED.value:
                    stats["dismissed"] += 1
                else:
                    stats["skipped"] += 1
            else:
                stats["failed"] += 1
        
        return stats
    
    async def retry_failed(
        self,
        run_result: SchedulerRunResult,
    ) -> SchedulerRunResult:
        """重试失败的结晶.
        
        Args:
            run_result: 上次运行结果
            
        Returns:
            新的运行结果
        """
        failed_gaps = [
            r.gap_id for r in run_result.details
            if not r.success and r.new_status == GapStatus.PENDING.value
        ]
        
        if not failed_gaps:
            return run_result
        
        logger.info(f"Retrying {len(failed_gaps)} failed crystallizations")
        
        # 获取缺口对象
        gaps_to_retry = []
        for gap_id in failed_gaps[:self._config.batch_size]:
            gap = await self._gap_repo.get_by_id(gap_id)
            if gap and gap.status == GapStatus.PENDING.value:
                gaps_to_retry.append(gap)
        
        # 重试处理
        retry_results = await self._process_gaps(gaps_to_retry)
        
        # 合并结果
        all_results = [
            r for r in run_result.details
            if r.gap_id not in failed_gaps[:self._config.batch_size]
        ] + retry_results
        
        stats = self._calculate_stats(all_results)
        
        return SchedulerRunResult(
            run_id=f"{run_result.run_id}_retry",
            started_at=run_result.started_at,
            completed_at=now_timestamp(),
            total_gaps=len(all_results),
            crystallized=stats["crystallized"],
            dismissed=stats["dismissed"],
            failed=stats["failed"],
            skipped=stats["skipped"],
            details=all_results,
        )

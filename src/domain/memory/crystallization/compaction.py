"""记忆数据压缩模块.

实现Episodic记忆压缩和图片归档。

功能追溯ID: F-MEM-006
"""

from __future__ import annotations
import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.domain.models.base import now_timestamp


class EpisodicCompression:
    """Episodic记忆压缩结果."""
    
    def __init__(
        self,
        student_id: str,
        compressed_data: Dict[str, Any],
        compression_ratio: float,
        original_count: int,
        compressed_count: int,
    ):
        """初始化压缩结果.
        
        Args:
            student_id: 学生ID
            compressed_data: 压缩后的数据
            compression_ratio: 压缩比
            original_count: 原始记录数
            compressed_count: 压缩后记录数
        """
        self.student_id = student_id
        self.compressed_data = compressed_data
        self.compression_ratio = compression_ratio
        self.original_count = original_count
        self.compressed_count = compressed_count
        self.compressed_at = now_timestamp()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典.
        
        Returns:
            字典表示
        """
        return {
            "student_id": self.student_id,
            "compression_ratio": self.compression_ratio,
            "original_count": self.original_count,
            "compressed_count": self.compressed_count,
            "compressed_at": self.compressed_at.isoformat(),
            "data_hash": self._compute_hash(),
        }
    
    def _compute_hash(self) -> str:
        """计算数据哈希.
        
        Returns:
            哈希值
        """
        data_str = json.dumps(self.compressed_data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()[:16]


class ImageArchiveRecord:
    """图片归档记录."""
    
    def __init__(
        self,
        image_id: str,
        original_url: str,
        archive_url: str,
        archive_date: datetime,
    ):
        """初始化归档记录.
        
        Args:
            image_id: 图片ID
            original_url: 原始URL
            archive_url: 归档URL
            archive_date: 归档日期
        """
        self.image_id = image_id
        self.original_url = original_url
        self.archive_url = archive_url
        self.archive_date = archive_date
        self.restored = False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "image_id": self.image_id,
            "original_url": self.original_url,
            "archive_url": self.archive_url,
            "archive_date": self.archive_date.isoformat(),
            "restored": self.restored,
        }


class MemoryCompaction:
    """记忆数据压缩器.
    
    管理Episodic记忆压缩和图片归档。
    """
    
    # 压缩阈值
    COMPRESSION_AGE_DAYS = 7  # 7天前的记录可压缩
    ARCHIVE_AGE_DAYS = 30  # 30天前的图片可归档
    
    def __init__(self):
        """初始化压缩器."""
        self._archive_records: List[ImageArchiveRecord] = []
        self._compression_records: List[EpisodicCompression] = []
    
    def compress_episodic_records(
        self,
        student_id: str,
        records: List[Dict[str, Any]],
        current_time: Optional[datetime] = None,
    ) -> EpisodicCompression:
        """压缩Episodic记忆记录.
        
        将多条记录聚合成语义摘要。
        
        Args:
            student_id: 学生ID
            records: 原始记录列表
            current_time: 当前时间
            
        Returns:
            压缩结果
        """
        current = current_time or now_timestamp()
        cutoff_date = current - timedelta(days=self.COMPRESSION_AGE_DAYS)
        
        # 筛选可压缩的记录
        compressible = [
            r for r in records
            if self._parse_time(r.get("timestamp", "")) and
            self._parse_time(r.get("timestamp", "")) < cutoff_date
        ]
        
        # 按类型分组聚合
        aggregated = self._aggregate_records(compressible)
        
        # 计算压缩比
        original_count = len(records)
        compressed_count = len(aggregated.get("clusters", []))
        
        ratio = (
            (original_count - compressed_count) / original_count
            if original_count > 0 else 0
        )
        
        compression = EpisodicCompression(
            student_id=student_id,
            compressed_data=aggregated,
            compression_ratio=ratio,
            original_count=original_count,
            compressed_count=compressed_count,
        )
        
        self._compression_records.append(compression)
        
        return compression
    
    def _aggregate_records(
        self,
        records: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """聚合记录.
        
        Args:
            records: 记录列表
            
        Returns:
            聚合结果
        """
        # 按知识标签分组
        clusters: Dict[str, List[Dict[str, Any]]] = {}
        
        for record in records:
            tags = record.get("knowledge_tags", [])
            primary_tag = tags[0] if tags else "general"
            
            if primary_tag not in clusters:
                clusters[primary_tag] = []
            clusters[primary_tag].append(record)
        
        # 生成摘要
        cluster_summaries = []
        for tag, cluster_records in clusters.items():
            summary = {
                "knowledge_tag": tag,
                "record_count": len(cluster_records),
                "error_types": list(set(
                    r.get("error_type", "unknown") for r in cluster_records
                )),
                "time_range": {
                    "start": min(r.get("timestamp", "") for r in cluster_records),
                    "end": max(r.get("timestamp", "") for r in cluster_records),
                },
                "accuracy_trend": self._compute_accuracy_trend(cluster_records),
            }
            cluster_summaries.append(summary)
        
        return {
            "clusters": cluster_summaries,
            "total_records": len(records),
            "aggregation_version": "1.0",
        }
    
    def _compute_accuracy_trend(
        self,
        records: List[Dict[str, Any]],
    ) -> str:
        """计算准确率趋势.
        
        Args:
            records: 记录列表
            
        Returns:
            趋势描述
        """
        if len(records) < 2:
            return "insufficient_data"
        
        # 按时间排序
        sorted_records = sorted(records, key=lambda r: r.get("timestamp", ""))
        
        # 分前后两半比较
        mid = len(sorted_records) // 2
        first_half = sorted_records[:mid]
        second_half = sorted_records[mid:]
        
        first_accuracy = sum(
            1 for r in first_half if r.get("is_correct", False)
        ) / len(first_half) if first_half else 0
        
        second_accuracy = sum(
            1 for r in second_half if r.get("is_correct", False)
        ) / len(second_half) if second_half else 0
        
        diff = second_accuracy - first_accuracy
        
        if diff > 0.1:
            return "improving"
        elif diff < -0.1:
            return "declining"
        else:
            return "stable"
    
    def archive_images(
        self,
        images: List[Dict[str, Any]],
        current_time: Optional[datetime] = None,
    ) -> List[ImageArchiveRecord]:
        """归档图片.
        
        Args:
            images: 图片列表
            current_time: 当前时间
            
        Returns:
            归档记录列表
        """
        current = current_time or now_timestamp()
        cutoff_date = current - timedelta(days=self.ARCHIVE_AGE_DAYS)
        
        archived = []
        
        for image in images:
            upload_time = self._parse_time(image.get("uploaded_at", ""))
            
            if upload_time and upload_time < cutoff_date:
                # 生成归档URL
                archive_url = self._generate_archive_url(image)
                
                record = ImageArchiveRecord(
                    image_id=image.get("image_id", ""),
                    original_url=image.get("url", ""),
                    archive_url=archive_url,
                    archive_date=current,
                )
                
                self._archive_records.append(record)
                archived.append(record)
        
        return archived
    
    def _generate_archive_url(self, image: Dict[str, Any]) -> str:
        """生成归档URL.
        
        Args:
            image: 图片数据
            
        Returns:
            归档URL
        """
        image_id = image.get("image_id", "unknown")
        return f"archive://{image_id}"
    
    def get_archive_stats(self) -> Dict[str, Any]:
        """获取归档统计.
        
        Returns:
            统计信息
        """
        return {
            "total_archived": len(self._archive_records),
            "total_compressed": len(self._compression_records),
            "avg_compression_ratio": (
                sum(c.compression_ratio for c in self._compression_records) /
                len(self._compression_records)
                if self._compression_records else 0
            ),
            "storage_saved_mb": self._estimate_storage_saved(),
        }
    
    def _estimate_storage_saved(self) -> float:
        """估算节省的存储空间(MB).
        
        Returns:
            节省的MB数
        """
        # 假设每条Episodic记录1KB，每张图片500KB
        episodic_saved = sum(
            c.original_count - c.compressed_count
            for c in self._compression_records
        ) * 0.001  # KB to MB
        
        image_saved = len(self._archive_records) * 0.5  # 500KB each
        
        return round(episodic_saved + image_saved, 2)
    
    def _parse_time(self, time_value: Any) -> Optional[datetime]:
        """解析时间值.
        
        Args:
            time_value: 时间值
            
        Returns:
            datetime对象或None
        """
        if isinstance(time_value, datetime):
            return time_value
        
        if isinstance(time_value, str):
            try:
                return datetime.fromisoformat(time_value.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        
        return None

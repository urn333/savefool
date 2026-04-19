"""作业服务.

封装作业相关的数据库操作，替代内存存储.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db import Homework, Question, Student
from src.infrastructure.db.enums import HomeworkStatus
from src.infrastructure.storage.repositories import (
    HomeworkRepository,
    QuestionRepository,
    StudentRepository,
)
from src.domain.models.base import generate_id


class HomeworkService:
    """作业服务.

    提供作业的创建、查询、更新、删除等操作，
    替代原来的 _homework_store 内存存储.
    """

    def __init__(self, session: AsyncSession):
        """初始化作业服务.

        Args:
            session: 数据库会话.
        """
        self.session = session
        self.homework_repo = HomeworkRepository(session)
        self.student_repo = StudentRepository(session)
        self.question_repo = QuestionRepository(session)

    async def ensure_student(
        self,
        student_id: str,
        name: str = "未知学生",
        grade: str = "未知",
    ) -> Student:
        """确保学生记录存在，不存在则创建.

        Args:
            student_id: 学生ID.
            name: 学生姓名.
            grade: 年级.

        Returns:
            学生记录.
        """
        student = await self.student_repo.get_by_id(student_id)
        if student is None:
            student = Student(
                student_id=student_id,
                name=name,
                grade=grade,
                preferred_subjects=[],
            )
            await self.student_repo.create(student)
        return student

    async def create_homework(
        self,
        student_id: str,
        subject: str,
        image_url: str,
        processed_image_url: Optional[str] = None,
        processed_image_path: Optional[str] = None,
        parent_description: Optional[str] = None,
        diagnosis_mode: str = "diagnosis",
        homework_id: Optional[str] = None,
    ) -> Homework:
        """创建作业记录.

        Args:
            student_id: 学生ID.
            subject: 学科.
            image_url: 原图URL.
            processed_image_url: 预处理后图片URL.
            processed_image_path: 预处理后图片本地路径.
            parent_description: 家长描述.
            diagnosis_mode: 诊断模式.
            homework_id: 指定作业ID（可选，默认自动生成）.

        Returns:
            创建的作业记录.
        """
        # 确保学生存在
        await self.ensure_student(student_id)

        homework = Homework(
            homework_id=homework_id or generate_id("hw"),
            student_id=student_id,
            subject=subject,
            page_count=1,
            image_urls=[image_url],
            status=HomeworkStatus.PENDING.value,
            processed_image_url=processed_image_url,
            parent_description=parent_description,
            diagnosis_mode=diagnosis_mode,
            error_count=0,
            total_count=0,
        )
        await self.homework_repo.create(homework)
        return homework

    async def get_homework(self, homework_id: str) -> Optional[Homework]:
        """获取作业详情.

        Args:
            homework_id: 作业ID.

        Returns:
            作业记录，不存在返回 None.
        """
        return await self.homework_repo.get_by_id(homework_id)

    async def update_homework_status(
        self,
        homework_id: str,
        status: str,
        **kwargs,
    ) -> Optional[Homework]:
        """更新作业状态.

        Args:
            homework_id: 作业ID.
            status: 新状态.
            **kwargs: 其他要更新的字段.

        Returns:
            更新后的作业记录，不存在返回 None.
        """
        homework = await self.homework_repo.get_by_id(homework_id)
        if homework is None:
            return None

        homework.status = status

        if status in (HomeworkStatus.COMPLETED.value, HomeworkStatus.FAILED.value):
            homework.completed_at = datetime.utcnow()

        for key, value in kwargs.items():
            if hasattr(homework, key):
                setattr(homework, key, value)

        await self.homework_repo.update(homework)
        return homework

    async def list_homeworks(
        self,
        student_id: str,
        subject: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Homework]:
        """获取学生作业列表.

        Args:
            student_id: 学生ID.
            subject: 学科筛选.
            status: 状态筛选.
            limit: 每页数量.
            offset: 偏移量.

        Returns:
            作业列表.
        """
        filters = {"student_id": student_id}
        if subject:
            filters["subject"] = subject
        if status:
            filters["status"] = status

        result = await self.homework_repo.find_many(
            order_by=Homework.created_at,
            desc_order=True,
            **filters,
        )
        # find_many 返回的是列表或 PageResult
        if isinstance(result, list):
            items = result
        else:
            items = result.items

        return items[offset:offset + limit]

    async def count_homeworks(
        self,
        student_id: str,
        subject: Optional[str] = None,
        status: Optional[str] = None,
    ) -> int:
        """统计作业数量.

        Args:
            student_id: 学生ID.
            subject: 学科筛选.
            status: 状态筛选.

        Returns:
            数量.
        """
        filters = {"student_id": student_id}
        if subject:
            filters["subject"] = subject
        if status:
            filters["status"] = status

        result = await self.homework_repo.find_many(**filters)
        if isinstance(result, list):
            return len(result)
        return result.total

    async def delete_homework(self, homework_id: str) -> bool:
        """删除作业.

        Args:
            homework_id: 作业ID.

        Returns:
            是否删除成功.
        """
        homework = await self.homework_repo.get_by_id(homework_id)
        if homework is None:
            return False
        await self.homework_repo.delete(homework)
        return True

    def homework_to_dict(self, homework: Homework) -> dict:
        """将作业ORM对象转换为字典.

        兼容原来的 _homework_store 数据结构.

        Args:
            homework: 作业ORM对象.

        Returns:
            字典.
        """
        return {
            "homework_id": homework.homework_id,
            "student_id": homework.student_id,
            "subject": homework.subject,
            "status": homework.status,
            "image_url": homework.image_urls[0] if homework.image_urls else None,
            "processed_image_url": homework.processed_image_url,
            "processed_image_path": getattr(homework, "processed_image_path", None),
            "parent_description": homework.parent_description,
            "diagnosis_mode": homework.diagnosis_mode,
            "created_at": int(homework.created_at.timestamp()) if homework.created_at else 0,
            "completed_at": int(homework.completed_at.timestamp()) if homework.completed_at else None,
            "error_count": homework.error_count,
            "total_count": homework.total_count,
            "diagnosis_result": homework.diagnosis_result,
            "raw_model_response": homework.raw_model_response,
        }

"""
数据模型：TaskStatus 枚举、TaskConfig、ProgressInfo、Task dataclass。
替代原来散布在代码里的裸 dict，提供类型安全与序列化支持。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TaskStatus(Enum):
    """任务生命周期状态"""
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    STOPPED = 'stopped'

    def __str__(self) -> str:
        return self.value


@dataclass
class TaskConfig:
    """训练任务配置参数（对应一次实验的全部输入）"""
    env_name: str = 'base'
    script_path: str = ''
    work_dir: str = ''
    dataset: str = 'cad38'
    dataset_path: str = ''
    max_epochs: int = 200
    batch_size: int = 64
    experiment_name: str = 'classification'

    def to_dict(self) -> dict:
        return {
            'env_name': self.env_name,
            'script_path': self.script_path,
            'work_dir': self.work_dir,
            'dataset': self.dataset,
            'dataset_path': self.dataset_path,
            'max_epochs': str(self.max_epochs),
            'batch_size': str(self.batch_size),
            'experiment_name': self.experiment_name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TaskConfig:
        return cls(
            env_name=str(data.get('env_name', 'base')),
            script_path=str(data.get('script_path', '')),
            work_dir=str(data.get('work_dir', '')),
            dataset=str(data.get('dataset', 'cad38')),
            dataset_path=str(data.get('dataset_path', '')),
            max_epochs=int(data.get('max_epochs', 200)),
            batch_size=int(data.get('batch_size', 64)),
            experiment_name=str(data.get('experiment_name', 'classification')),
        )


@dataclass
class ProgressInfo:
    """训练进度快照（用于进度条与状态文本）"""
    epoch: int = 0
    total_epochs: int = 200
    progress_percent: float = 0.0
    status_text: str = "准备中"

    def to_dict(self) -> dict:
        return {
            'epoch': self.epoch,
            'total_epochs': self.total_epochs,
            'progress_percent': self.progress_percent,
            'status_text': self.status_text,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ProgressInfo:
        return cls(
            epoch=int(data.get('epoch', 0)),
            total_epochs=int(data.get('total_epochs', 200)),
            progress_percent=float(data.get('progress_percent', 0)),
            status_text=str(data.get('status_text', '准备中')),
        )

    def copy(self) -> ProgressInfo:
        return ProgressInfo(
            epoch=self.epoch,
            total_epochs=self.total_epochs,
            progress_percent=self.progress_percent,
            status_text=self.status_text,
        )


@dataclass
class Task:
    """训练任务完整状态对象"""
    id: int
    config: TaskConfig
    gpu_id: int = 0
    wait_seconds: int = 0
    status: TaskStatus = TaskStatus.PENDING
    progress_info: ProgressInfo = field(default_factory=ProgressInfo)
    add_time: str = ''
    start_time: Optional[str] = None
    end_time: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'config': self.config.to_dict(),
            'gpu_id': self.gpu_id,
            'wait_seconds': self.wait_seconds,
            'status': self.status.value,
            'progress_info': self.progress_info.to_dict(),
            'add_time': self.add_time,
            'start_time': self.start_time,
            'end_time': self.end_time,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Task:
        status_str = data.get('status', 'pending')
        try:
            status = TaskStatus(status_str)
        except ValueError:
            status = TaskStatus.PENDING
        return cls(
            id=int(data['id']),
            config=TaskConfig.from_dict(data.get('config', {})),
            gpu_id=int(data.get('gpu_id', 0)),
            wait_seconds=int(data.get('wait_seconds', 0)),
            status=status,
            progress_info=ProgressInfo.from_dict(data.get('progress_info', {})),
            add_time=str(data.get('add_time', '')),
            start_time=data.get('start_time'),
            end_time=data.get('end_time'),
        )

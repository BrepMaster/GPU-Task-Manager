"""
数据模型单元测试：TaskStatus、TaskConfig、ProgressInfo、Task。
纯逻辑测试，不需要 PyQt5 / GPU / nvidia-smi。
"""
import json
import pytest

from gpu_manager.core.models import TaskStatus, TaskConfig, ProgressInfo, Task


# ── TaskStatus ──────────────────────────────────────────────────────────────

class TestTaskStatus:
    def test_values(self):
        assert TaskStatus.PENDING.value == 'pending'
        assert TaskStatus.RUNNING.value == 'running'
        assert TaskStatus.COMPLETED.value == 'completed'
        assert TaskStatus.FAILED.value == 'failed'
        assert TaskStatus.STOPPED.value == 'stopped'

    def test_str_returns_value(self):
        assert str(TaskStatus.PENDING) == 'pending'

    def test_from_value(self):
        assert TaskStatus('running') == TaskStatus.RUNNING

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            TaskStatus('unknown')


# ── TaskConfig ──────────────────────────────────────────────────────────────

class TestTaskConfig:
    def test_defaults(self):
        cfg = TaskConfig()
        assert cfg.env_name == 'base'
        assert cfg.script_path == ''
        assert cfg.max_epochs == 200
        assert cfg.batch_size == 64
        assert cfg.experiment_name == 'classification'

    def test_custom_values(self):
        cfg = TaskConfig(
            env_name='3dse',
            script_path='/path/to/train.py',
            max_epochs=500,
            batch_size=128,
            experiment_name='segmentation',
        )
        assert cfg.env_name == '3dse'
        assert cfg.max_epochs == 500
        assert cfg.experiment_name == 'segmentation'

    def test_to_dict(self):
        cfg = TaskConfig(max_epochs=100, batch_size=32)
        d = cfg.to_dict()
        assert d['max_epochs'] == '100'   # 序列化为字符串
        assert d['batch_size'] == '32'
        assert d['env_name'] == 'base'

    def test_from_dict(self):
        d = {
            'env_name': 'myenv',
            'script_path': '/tmp/run.py',
            'max_epochs': '300',
            'batch_size': '64',
            'experiment_name': 'test',
        }
        cfg = TaskConfig.from_dict(d)
        assert cfg.env_name == 'myenv'
        assert cfg.max_epochs == 300    # 反序列化为 int
        assert cfg.batch_size == 64

    def test_round_trip(self):
        original = TaskConfig(
            env_name='3dse',
            script_path='/tmp/train.py',
            max_epochs=150,
            batch_size=256,
            experiment_name='exp_round',
        )
        restored = TaskConfig.from_dict(original.to_dict())
        assert restored == original


# ── ProgressInfo ────────────────────────────────────────────────────────────

class TestProgressInfo:
    def test_defaults(self):
        pi = ProgressInfo()
        assert pi.epoch == 0
        assert pi.total_epochs == 200
        assert pi.progress_percent == 0.0
        assert pi.status_text == "准备中"

    def test_copy_is_independent(self):
        pi = ProgressInfo(epoch=5, total_epochs=10, progress_percent=50.0)
        cp = pi.copy()
        cp.epoch = 99
        assert pi.epoch == 5  # 原对象未受影响

    def test_round_trip(self):
        pi = ProgressInfo(epoch=10, total_epochs=100, progress_percent=10.0,
                          status_text='Epoch 10/100')
        d = pi.to_dict()
        restored = ProgressInfo.from_dict(d)
        assert restored == pi


# ── Task ────────────────────────────────────────────────────────────────────

class TestTask:
    def test_minimal_creation(self):
        t = Task(id=1, config=TaskConfig())
        assert t.id == 1
        assert t.status == TaskStatus.PENDING
        assert t.start_time is None
        assert t.end_time is None

    def test_full_creation(self):
        cfg = TaskConfig(experiment_name='full_test')
        pi = ProgressInfo(epoch=5, total_epochs=50, progress_percent=10.0)
        t = Task(
            id=42, config=cfg, gpu_id=1, wait_seconds=60,
            status=TaskStatus.RUNNING, progress_info=pi,
            add_time='2026-01-01 00:00:00',
            start_time='2026-01-01 00:01:00',
            end_time=None,
        )
        assert t.id == 42
        assert t.config.experiment_name == 'full_test'
        assert t.status == TaskStatus.RUNNING
        assert t.progress_info.epoch == 5

    def test_to_dict(self):
        t = Task(id=7, config=TaskConfig(experiment_name='d'))
        d = t.to_dict()
        assert d['id'] == 7
        assert d['status'] == 'pending'
        assert d['config']['experiment_name'] == 'd'

    def test_from_dict(self):
        d = {
            'id': 99,
            'config': {'experiment_name': 'restored', 'max_epochs': '400'},
            'gpu_id': 2,
            'status': 'completed',
            'add_time': '2026-06-01 12:00:00',
        }
        t = Task.from_dict(d)
        assert t.id == 99
        assert t.config.max_epochs == 400
        assert t.status == TaskStatus.COMPLETED
        assert t.start_time is None

    def test_from_dict_invalid_status_falls_back(self):
        d = {'id': 1, 'config': {}, 'status': 'bogus'}
        t = Task.from_dict(d)
        assert t.status == TaskStatus.PENDING

    def test_json_serializable(self):
        """确认 to_dict() 的输出可被 json.dumps 直接序列化"""
        t = Task(id=5, config=TaskConfig(script_path='/a/b.py'))
        s = json.dumps(t.to_dict(), ensure_ascii=False)
        assert '"id": 5' in s

    def test_round_trip(self):
        original = Task(
            id=11,
            config=TaskConfig(env_name='env', script_path='/s.py',
                              max_epochs=20, batch_size=8,
                              experiment_name='rt'),
            gpu_id=3, wait_seconds=120,
            status=TaskStatus.STOPPED,
            progress_info=ProgressInfo(epoch=2, total_epochs=20,
                                       progress_percent=10.0,
                                       status_text='Epoch 2/20'),
            add_time='2026-01-01', start_time='2026-01-02',
            end_time='2026-01-03',
        )
        restored = Task.from_dict(original.to_dict())
        assert restored == original

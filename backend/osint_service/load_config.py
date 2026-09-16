# -*- coding: utf-8 -*-
import yaml

try:
    class Config:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                # 如果值是字典，则递归转换为对象
                if isinstance(value, dict):
                    value = Config(**value)
                setattr(self, key, value)

        def __repr__(self):
            return str(self.__dict__)
        
        def __getattr__(self, name):
            return None

    def load_config(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)

        return Config(**data)

    import os
    config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.yml')
    if not os.path.exists(config_file):
        config_file = 'config.yml'
    config = load_config(config_file)
except Exception as e:
    import sys
    sys.stderr.write(f"CRITICAL: 加载配置文件失败: {e}\n")
    sys.exit(1)
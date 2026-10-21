import yaml
import pandas as pd
from pathlib import Path


class Config:
    # Простой доступ ко всем конфигам проекта
    def __init__(self, project_root=None):
        if project_root is None:
            project_root = Path(__file__).parent.parent
        self.root = Path(project_root)

        self.case = self._load_yaml('config/case_inputs.yml')
        self.market = self._load_yaml('config/market_benchmarks.yml')
        self.product = self._load_yaml('config/product_paths.yml')
        self.segments = pd.read_csv(self.root / 'data' / 'segments.csv')
        self.tariffs = pd.read_csv(self.root / 'data' / 'tariff_options.csv')

    def _load_yaml(self, rel_path):
        with open(self.root / rel_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
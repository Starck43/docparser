
from typing import Callable, List

from app.utils.console import console, print_success


class DataPipeline:
	"""Универсальный пайплайн обработки данных"""

	def __init__(self, processor: Callable, writer: Callable, batch_size: int = 100):
		self.processor = processor
		self.writer = writer
		self.batch_size = batch_size

	def run(self, data: List, description: str = "Обработка"):
		"""Запускает пайплайн обработки"""
		console.print(f"🔄 {description}: {len(data)} элементов", style="bold")

		total = len(data)
		for i in range(0, total, self.batch_size):
			batch = data[i:i + self.batch_size]
			processed = self.processor(batch)
			self.writer(processed)

			progress = min(i + len(batch), total)
			console.print(f"📊 Обработано: {progress}/{total}", style="dim")

		print_success(f"{description} завершена")

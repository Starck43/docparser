from pathlib import Path

import typer

from app.db import init_db, get_session
from app.export import export_to_console, export_to_xls
from app.models import Document
from app.services import parser

cli = typer.Typer()


@cli.command()
def parse_file(file: Path):
	"""Распарсить один файл и сохранить в базу"""
	text = parser.parse_file(file)
	for session in get_session():
		doc = Document(filename=Path(file).name, content_text=text)
		session.add(doc)
		session.commit()
		typer.echo(f"Сохранено: {doc.filename} (id={doc.id})")


@cli.command()
def parse_folder(folder: str):
	"""Пройти по файлам в папке и вывести короткий превью извлечённого текста"""
	folder = Path(folder)
	if not folder.exists():
		typer.echo("Папка не существует")
		raise typer.Exit(code=1)

	for p in sorted(folder.iterdir()):
		if p.is_file():
			text = parser.parse_file(p)
			typer.echo(f"=== {p.name} ===")
			typer.echo((text or "<пустой результат>")[:300])
			typer.echo("...")


@cli.command()
def initdb():
	"""Создать базу данных"""
	init_db()
	typer.echo("DB initialized")


@cli.command()
def export_console():
	"""Вывести все документы в консоль"""
	for session in get_session():
		export_to_console(session)


@cli.command()
def export_xls(output: Path = Path("export.xlsx")):
	"""Экспортировать документы в XLS"""
	for session in get_session():
		export_to_xls(session, output)


if __name__ == "__main__":
	cli()

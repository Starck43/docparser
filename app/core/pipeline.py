from pathlib import Path

from rich.progress import Progress, TextColumn, BarColumn

from app.config import settings
from app.crud import create_document, update_document, get_document_by_slug, bulk_save_documents
from app.db import get_db
from app.models import DocumentCreate
from app.services.files import convert_file_to_text
from app.services.parser import DocumentParser
from app.utils.base import format_string_list
from app.utils.console import console, print_error


def parse_files_pipeline(
    files: list[Path],
    year: int,
    save_to_db: bool = True,
    update_mode: bool = False,
    use_bulk: bool = True,
) -> int:
    """
    Универсальный пайплайн для парсинга и сохранения документов.
    Работает с Progress, буферизацией и подсчётом статистики.
    """

    parser = DocumentParser()
    bulk_buffer: list[DocumentCreate] = []
    processed = skipped = updated = 0
    flush_size = settings.BATCH_FLUSH_SIZE

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn(" {task.completed}/{task.total}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("📂 Обработка файлов...", total=len(files))

        for i, file_path in enumerate(files, 1):
            try:
                # Этап 1. Чтение
                data = convert_file_to_text(file_path)
                if not data or not data[0]:
                    skipped += 1
                    progress.advance(task)
                    continue

                # Этап 2. Парсинг
                document_data = parser.parse_document(str(file_path.name), data=data, year=year)

                # Проверка на планы (если нет — пропускаем)
                if not document_data.plans:
                    status = parser.format_status(document_data.validation_errors, True, False)
                    console.print(f"[{i:03d}/{len(files)}]: [grey]{file_path.name}[/grey] ... {status}")
                    skipped += 1
                    progress.advance(task)
                    continue

                # Этап 3. Проверка в БД
                with next(get_db()) as db:
                    existing_doc = get_document_by_slug(db, document_data.slug)

                    if existing_doc:
                        if update_mode:
                            if save_to_db and not use_bulk:
                                document_data = update_document(db, existing_doc.id, document_data)
                            updated += 1
                        else:
                            status = parser.format_status(document_data.validation_errors, True, update_mode)
                            console.print(f"[{i:03d}/{len(files)}]: [grey]{file_path.name}[/grey] ... {status}")
                            skipped += 1
                            progress.advance(task)
                            continue
                    else:
                        if save_to_db and not use_bulk:
                            document_data = create_document(db, document_data)

                    # Bulk режим — копим в буфер
                    if save_to_db and use_bulk:
                        bulk_buffer.append(document_data)

                        # Если буфер переполнен → сбрасываем в БД
                        if len(bulk_buffer) >= flush_size:
                            with next(get_db()) as db:
                                bulk_save_documents(db, bulk_buffer, update_mode=update_mode)
                            bulk_buffer.clear()

                processed += 1

                # Этап 4. Статус в консоль
                status = parser.format_status(document_data.validation_errors, bool(existing_doc), update_mode)
                console.print(f"[{i:03d}/{len(files)}]: [gray]{file_path.name}[/gray] ... {status}")

                if document_data.validation_errors:
                    console.print(
                        f"          ⚠️  [red]{format_string_list(document_data.validation_errors, separator=', ')}[/red]"
                    )

            except Exception as e:
                print_error(f"Ошибка обработки {file_path.name}: {e}")
                skipped += 1

            progress.advance(task)

        # Финальный сброс (если что-то осталось в буфере)
        if save_to_db and use_bulk and bulk_buffer:
            with next(get_db()) as db:
                bulk_save_documents(db, bulk_buffer, update_mode=update_mode)

    # Итоговая статистика
    console.print("\n" + "=" * 50, style="dim")
    console.print(f"📊 Статистика обработки:", style="bold")
    console.print(f"   Всего документов: {len(files)}")
    console.print(f"   Обработано: {processed}")
    console.print(f"   Обновлено: {updated}")
    console.print(f"   Пропущено: {skipped}")
    console.print("=" * 50, style="dim")

    return processed

"""
Test per cloud_model.py — CloudFileModel e TagDelegate.
"""

import json

import pytest
from PyQt6.QtCore import Qt, QModelIndex
from PyQt6.QtWidgets import QApplication

from database import FileRecord
from gui.cloud_model import CloudFileModel, TagDelegate


@pytest.fixture
def model():
    """CloudFileModel vuoto pronto per i test."""
    return CloudFileModel()


@pytest.fixture
def model_with_data(sample_file_records):
    """CloudFileModel popolato con 3 file di esempio."""
    model = CloudFileModel()
    model.set_files(sample_file_records)
    return model


class TestCloudFileModelInit:
    """Test di inizializzazione del modello."""

    def test_initial_state_empty(self, model):
        """Il modello appena creato è vuoto."""
        assert model.rowCount() == 0
        assert model.columnCount() == 7
        assert model.file_count() == 0
        assert model.checked_count() == 0

    def test_column_count(self, model):
        """Il modello ha 7 colonne."""
        assert model.columnCount() == 7
        assert model.COLUMNS == ["", "Nome", "Dimensione", "Tipo", "Data", "Canale", "Tags"]

    def test_checkbox_column_index(self, model):
        """La colonna 0 è la colonna checkbox."""
        assert model.CHECKBOX_COL == 0


class TestSetFiles:
    """Test del metodo set_files e conteggi."""

    def test_set_files_populates_model(self, model, sample_file_records):
        """set_files popola il modello con i file."""
        model.set_files(sample_file_records)
        assert model.rowCount() == 3
        assert model.file_count() == 3
        assert model.checked_count() == 0

    def test_set_files_clears_previous(self, model, sample_file_records):
        """set_files sostituisce i file esistenti."""
        model.set_files(sample_file_records)
        model.set_files([])
        assert model.rowCount() == 0
        assert model.file_count() == 0

    def test_set_files_resets_checked(self, model, sample_file_records):
        """set_files resetta le checkbox."""
        model.set_files(sample_file_records)
        model.check_all()
        assert model.checked_count() == 3
        model.set_files(sample_file_records)
        assert model.checked_count() == 0


class TestDisplayData:
    """Test dei dati visualizzati nel modello."""

    def test_filename_display(self, model_with_data):
        """La colonna 1 mostra il nome file (original_filename se presente)."""
        idx = model_with_data.index(0, 1)
        data = model_with_data.data(idx, Qt.ItemDataRole.DisplayRole)
        assert data == "report.pdf"  # original_filename del primo file

    def test_fallback_to_filename(self, model_with_data):
        """Se original_filename è vuoto, mostra filename."""
        idx = model_with_data.index(2, 1)  # terzo file, original_filename=""
        data = model_with_data.data(idx, Qt.ItemDataRole.DisplayRole)
        assert data == "dati.xlsx"

    def test_size_formatting(self, model_with_data):
        """La colonna 2 mostra la dimensione formattata."""
        idx = model_with_data.index(0, 2)
        data = model_with_data.data(idx, Qt.ItemDataRole.DisplayRole)
        assert "1000.0 KB" in data or "MB" in data or "KB" in data

    def test_mime_type_display(self, model_with_data):
        """La colonna 3 mostra il mime type."""
        idx = model_with_data.index(0, 3)
        data = model_with_data.data(idx, Qt.ItemDataRole.DisplayRole)
        assert data == "application/pdf"

    def test_date_display(self, model_with_data):
        """La colonna 4 mostra la data di upload."""
        idx = model_with_data.index(0, 4)
        data = model_with_data.data(idx, Qt.ItemDataRole.DisplayRole)
        assert data == "2026-06-01T10:00:00"

    def test_channel_display(self, model_with_data, channel_names):
        """La colonna 5 mostra il nome del canale."""
        model_with_data.set_channel_names(channel_names)
        idx = model_with_data.index(0, 5)
        data = model_with_data.data(idx, Qt.ItemDataRole.DisplayRole)
        assert data == "Canale Test 1"

    def test_channel_fallback_to_id(self, model_with_data):
        """Senza channel_names, mostra l'ID numerico."""
        idx = model_with_data.index(0, 5)
        data = model_with_data.data(idx, Qt.ItemDataRole.DisplayRole)
        assert data == "-1001111111111"

    def test_tags_display(self, model_with_data):
        """La colonna 6 mostra i tags."""
        idx = model_with_data.index(0, 6)
        data = model_with_data.data(idx, Qt.ItemDataRole.DisplayRole)
        assert data == "lavoro"

    def test_invalid_index_returns_none(self, model_with_data):
        """Indice non valido restituisce None."""
        assert model_with_data.data(QModelIndex(), Qt.ItemDataRole.DisplayRole) is None


class TestFormatSize:
    """Test della formattazione dimensioni."""

    def test_bytes(self, model):
        assert model.format_size(0) == "0 B"
        assert model.format_size(500) == "500 B"
        assert model.format_size(1023) == "1023 B"

    def test_kilobytes(self, model):
        result = model.format_size(1024)
        assert "KB" in result

    def test_megabytes(self, model):
        result = model.format_size(1024 * 1024)
        assert "MB" in result

    def test_gigabytes(self, model):
        result = model.format_size(1024 * 1024 * 1024)
        assert "GB" in result


class TestCheckboxes:
    """Test della logica delle checkbox."""

    def test_initial_state_unchecked(self, model_with_data):
        """All'inizio nessuna checkbox è selezionata."""
        idx = model_with_data.index(0, 0)
        state = model_with_data.data(idx, Qt.ItemDataRole.CheckStateRole)
        assert state == Qt.CheckState.Unchecked

    def test_check_all(self, model_with_data):
        """check_all seleziona tutte le righe."""
        model_with_data.check_all()
        assert model_with_data.checked_count() == 3
        assert model_with_data.is_all_checked()

    def test_uncheck_all(self, model_with_data):
        """uncheck_all deseleziona tutte le righe."""
        model_with_data.check_all()
        model_with_data.uncheck_all()
        assert model_with_data.checked_count() == 0
        assert not model_with_data.is_all_checked()

    def test_toggle_all_to_checked(self, model_with_data):
        """toggle_all su modello unchecked -> check_all."""
        assert model_with_data.checked_count() == 0
        model_with_data.toggle_all()
        assert model_with_data.checked_count() == 3

    def test_toggle_all_to_unchecked(self, model_with_data):
        """toggle_all su modello checked -> uncheck_all."""
        model_with_data.check_all()
        model_with_data.toggle_all()
        assert model_with_data.checked_count() == 0

    def test_get_checked_files(self, model_with_data):
        """get_checked_files restituisce solo i file selezionati."""
        model_with_data.check_all()
        checked = model_with_data.get_checked_files()
        assert len(checked) == 3
        # Verifica ordinamento
        assert checked[0].message_id == 1001

    def test_get_checked_files_empty(self, model_with_data):
        """Se nessuna checkbox è selezionata, restituisce lista vuota."""
        assert model_with_data.get_checked_files() == []

    def test_setData_checkbox_toggle(self, model_with_data):
        """setData con CheckStateRole toggle- la checkbox."""
        idx = model_with_data.index(0, 0)
        model_with_data.setData(idx, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
        assert model_with_data.checked_count() == 1
        assert 0 in model_with_data._checked

        model_with_data.setData(idx, Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
        assert model_with_data.checked_count() == 0

    def test_setData_tags_column(self, model_with_data):
        """setData sulla colonna Tags aggiorna il tag."""
        idx = model_with_data.index(0, 6)
        result = model_with_data.setData(idx, "nuovo_tag", Qt.ItemDataRole.EditRole)
        assert result is True
        assert model_with_data._files[0].tags == "nuovo_tag"

    def test_setData_tags_on_transfer_row_fails(self, model):
        """setData su una transfer row deve fallire."""
        model.add_transfer("op1", "uploading.txt", 0, "", -1001111111111, "upload")
        idx = model.index(0, 6)  # transfer row è alla posizione 0
        result = model.setData(idx, "tag", Qt.ItemDataRole.EditRole)
        assert result is False

    def test_header_shows_checkbox_state(self, model_with_data):
        """L'header della colonna 0 mostra ☐, ◐, o ☑."""
        hdr = model_with_data.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
        assert hdr == "☐"

        model_with_data.check_all()
        hdr = model_with_data.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
        assert hdr == "☑"

        # Deseleziona solo un file -> ◐
        idx = model_with_data.index(0, 0)
        model_with_data.setData(idx, Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
        hdr = model_with_data.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
        assert hdr == "◐"


class TestTransfers:
    """Test delle righe di trasferimento."""

    def test_add_transfer(self, model_with_data):
        """add_transfer aggiunge una riga di trasferimento all'inizio."""
        initial_count = model_with_data.rowCount()
        model_with_data.add_transfer("op1", "uploading.txt", 1024, "text/plain",
                                     -1001111111111, "upload")
        assert model_with_data.rowCount() == initial_count + 1
        # La transfer row è la prima
        idx = model_with_data.index(0, 1)
        display = model_with_data.data(idx, Qt.ItemDataRole.DisplayRole)
        assert "⬆" in display
        assert "uploading.txt" in display

    def test_add_download_transfer(self, model_with_data):
        """Transfer di download mostra icona ⬇."""
        model_with_data.add_transfer("op2", "downloading.txt", 2048, "text/plain",
                                     -1001111111111, "download")
        idx = model_with_data.index(0, 1)
        display = model_with_data.data(idx, Qt.ItemDataRole.DisplayRole)
        assert "⬇" in display

    def test_transfer_font_is_italic(self, model_with_data):
        """Le righe di trasferimento hanno font italic."""
        model_with_data.add_transfer("op1", "test.txt", 100, "text/plain",
                                     -1001111111111, "upload")
        idx = model_with_data.index(0, 1)
        font = model_with_data.data(idx, Qt.ItemDataRole.FontRole)
        assert font is not None
        assert font.italic()

    def test_remove_transfer(self, model_with_data):
        """remove_transfer rimuove la riga di trasferimento."""
        model_with_data.add_transfer("op1", "test.txt", 100, "text/plain",
                                     -1001111111111, "upload")
        assert model_with_data.rowCount() == 4
        model_with_data.remove_transfer("op1")
        assert model_with_data.rowCount() == 3

    def test_get_file_after_transfer(self, model_with_data):
        """get_file su una riga dopo le transfer rows restituisce il file corretto."""
        model_with_data.add_transfer("op1", "uploading.txt", 100, "text/plain",
                                     -1001111111111, "upload")
        # Il terzo file originale è all'indice 3 (0 = transfer, 1-2-3 = file)
        idx = model_with_data.index(1, 1)  # primo file originale
        file = model_with_data.get_file(idx)
        assert file.message_id == 1001

    def test_transfer_row_no_checkbox(self, model_with_data):
        """Le righe di trasferimento non hanno checkbox."""
        model_with_data.add_transfer("op1", "test.txt", 100, "text/plain",
                                     -1001111111111, "upload")
        idx = model_with_data.index(0, 0)
        state = model_with_data.data(idx, Qt.ItemDataRole.CheckStateRole)
        assert state is None


class TestFlags:
    """Test dei flags delle celle."""

    def test_valid_index_has_basic_flags(self, model_with_data):
        """Un indice valido ha ItemIsEnabled e ItemIsSelectable."""
        idx = model_with_data.index(0, 1)
        flags = model_with_data.flags(idx)
        assert flags & Qt.ItemFlag.ItemIsEnabled
        assert flags & Qt.ItemFlag.ItemIsSelectable

    def test_tags_column_is_editable(self, model_with_data):
        """La colonna 6 (Tags) deve essere editabile."""
        idx = model_with_data.index(0, 6)
        flags = model_with_data.flags(idx)
        assert flags & Qt.ItemFlag.ItemIsEditable

    def test_non_tags_column_is_not_editable(self, model_with_data):
        """Le altre colonne non sono editabili."""
        idx = model_with_data.index(0, 1)
        flags = model_with_data.flags(idx)
        assert not (flags & Qt.ItemFlag.ItemIsEditable)

    def test_file_rows_are_draggable(self, model_with_data):
        """Le righe di file (non transfer) sono draggable."""
        # Usa una colonna non-checkbox (colonna 1) perché la colonna 0
        # restituisce solo ItemIsEnabled|ItemIsSelectable senza DragEnabled
        idx = model_with_data.index(0, 1)
        flags = model_with_data.flags(idx)
        assert flags & Qt.ItemFlag.ItemIsDragEnabled

    def test_invalid_index_no_flags(self, model_with_data):
        """Indice non valido -> NoItemFlags."""
        assert model_with_data.flags(QModelIndex()) == Qt.ItemFlag.NoItemFlags


class TestDragAndDrop:
    """Test dei dati di drag & drop."""

    def test_mimeData_contains_custom_format(self, model_with_data):
        """Il MIME data contiene il formato custom application/x-tgmdrive-cloud-file."""
        idx = model_with_data.index(0, 0)
        mime = model_with_data.mimeData([idx])
        assert mime.hasFormat("application/x-tgmdrive-cloud-file")

    def test_mimeData_json_content(self, model_with_data):
        """Il contenuto JSON del MIME data è corretto."""
        idx = model_with_data.index(0, 0)
        mime = model_with_data.mimeData([idx])
        data = json.loads(bytes(mime.data("application/x-tgmdrive-cloud-file")).decode())
        assert len(data) == 1
        assert data[0]["message_id"] == 1001
        assert data[0]["filename"] == "doc.pdf"
        assert data[0]["channel_id"] == -1001111111111
        assert data[0]["original_filename"] == "report.pdf"

    def test_mimeData_multiple_files(self, model_with_data):
        """Trascinamento di più file."""
        idx1 = model_with_data.index(0, 0)
        idx2 = model_with_data.index(1, 0)
        mime = model_with_data.mimeData([idx1, idx2])
        data = json.loads(bytes(mime.data("application/x-tgmdrive-cloud-file")).decode())
        assert len(data) == 2

    def test_mimeData_excludes_transfer_rows(self, model_with_data):
        """Le righe di trasferimento sono escluse dal drag."""
        model_with_data.add_transfer("op1", "transfer.txt", 100, "text/plain",
                                     -1001111111111, "upload")
        idx = model_with_data.index(0, 0)  # transfer row
        mime = model_with_data.mimeData([idx])
        assert not mime.hasFormat("application/x-tgmdrive-cloud-file")


class TestHeaderData:
    """Test dei dati di intestazione."""

    def test_header_labels(self, model):
        """Le intestazioni delle colonne devono corrispondere a COLUMNS."""
        for i, expected in enumerate(model.COLUMNS):
            if i == 0:
                # La colonna 0 mostra lo stato checkbox
                hdr = model.headerData(i, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
                assert hdr in ("☐", "☑", "◐")
            else:
                hdr = model.headerData(i, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
                assert hdr == expected

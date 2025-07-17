from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox, QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt
from ..backend.storage_db import get_os_cadastros, update_status_os
import os

class StatusOSPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.status_nomes = [
            "Orçamento",
            "Aguardando aprovação",
            "Aprovado",
            "Em manutenção",
            "Manutenção em andamento",
            "Manutenção finalizada",
            "Aguardando entrega",
            "Entregue"
        ]
        self._setup_ui()
        self._load_os_combobox()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- Checkboxes em duas linhas ---
        self.status_checkboxes = []
        group = QGroupBox("Status OS")
        vbox = QVBoxLayout(group)
        hbox1 = QHBoxLayout()
        hbox2 = QHBoxLayout()
        for i, nome in enumerate(self.status_nomes):
            cb = QCheckBox(nome)
            cb.stateChanged.connect(self._on_status_checkbox_changed)
            if i < 4:
                hbox1.addWidget(cb)
            else:
                hbox2.addWidget(cb)
            self.status_checkboxes.append(cb)
        vbox.addLayout(hbox1)
        vbox.addLayout(hbox2)
        layout.addWidget(group)

        # --- ComboBox editável de OS ---
        self.cb_os = QComboBox()
        self.cb_os.setEditable(True)
        self.cb_os.setPlaceholderText("Selecione ou digite a OS...")
        self.cb_os.currentIndexChanged.connect(self._on_os_selected)
        icon_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "imagens", "seta.png"
        ))
        icon_url = icon_path.replace("\\", "/")
        self.cb_os.setStyleSheet(f"""
        QComboBox {{
            padding-right: 36px;
        }}
        QComboBox::drop-down {{
            width: 36px;
            subcontrol-origin: padding;
            subcontrol-position: top right;
            border: none;
        }}
        QComboBox::down-arrow {{
            image: url({icon_url});
            width: 32px;
            height: 32px;
        }}
        """)
        layout.addWidget(self.cb_os)

        # --- Tabela vertical (Campo | Valor) ---
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Campo", "Valor"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setStyleSheet("QTableWidget { background: #1b4d7a; border: none; color: white; gridline-color: #3a6ea5; } QTableWidget::item { background: transparent; color: white; border: none; } QHeaderView::section { background: #001933; color: #FFF; border: none; font-weight: bold; }")
        self.table.setShowGrid(True)
        # Ajustar a coluna 'Valor' para preencher o espaço
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, header.ResizeMode.Stretch)
        layout.addWidget(self.table)

        # --- Botão atualizar status ---
        self.btn_atualizar = QPushButton("Atualizar Status")
        self.btn_atualizar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_atualizar.clicked.connect(self._on_atualizar_status_clicked)
        layout.addWidget(self.btn_atualizar)

    def _load_os_combobox(self):
        self.cb_os.blockSignals(True)
        self.cb_os.clear()
        self.os_data = get_os_cadastros()  # Lista de dicts
        for os_item in self.os_data:
            self.cb_os.addItem(str(os_item.get("os", "")))
        self.cb_os.blockSignals(False)
        if self.cb_os.count() > 0:
            self.cb_os.setCurrentIndex(0)
            self._on_os_selected(0)

    def _on_status_checkbox_changed(self, state):
        sender = self.sender()
        if state == 2:  # Checked
            for cb in self.status_checkboxes:
                if cb is not sender:
                    cb.setChecked(False)

    def _formatar_nome_campo(self, campo):
        # Troca _ por espaço e coloca a primeira letra maiúscula de cada palavra
        return str(campo).replace('_', ' ').title()

    def _on_os_selected(self, idx):
        if idx < 0 or idx >= len(self.os_data):
            self.table.setRowCount(0)
            return
        os_item = self.os_data[idx]
        # Atualiza checkboxes
        for cb in self.status_checkboxes:
            cb.setChecked(cb.text() == os_item.get("status", ""))
        # Atualiza tabela
        campos = [
            ("cliente", os_item.get("cliente", "")),
            ("modelo", os_item.get("modelo", "")),
            ("os", os_item.get("os", "")),
            ("entrada_equip", os_item.get("entrada_equip", "")),
            ("tecnico", os_item.get("tecnico", "")),
            ("avaliacao_tecnica", os_item.get("avaliacao_tecnica", "")),
            ("causa_provavel", os_item.get("causa_provavel", "")),
            ("status", os_item.get("status", "")),
        ]
        self.table.setRowCount(len(campos))
        for i, (campo, valor) in enumerate(campos):
            valor_str = "" if valor is None else str(valor)
            item_campo = QTableWidgetItem(self._formatar_nome_campo(campo) + ":")
            font = item_campo.font()
            font.setBold(True)
            item_campo.setFont(font)
            self.table.setItem(i, 0, item_campo)
            self.table.setItem(i, 1, QTableWidgetItem(valor_str))
        self.table.resizeColumnsToContents()
        # Sempre garantir que a coluna 'Valor' preencha o espaço
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, header.ResizeMode.Stretch)

    def _on_atualizar_status_clicked(self):
        idx = self.cb_os.currentIndex()
        if idx < 0 or idx >= len(self.os_data):
            return
        novo_status = None
        for cb in self.status_checkboxes:
            if cb.isChecked():
                novo_status = cb.text()
                break
        if not novo_status:
            QMessageBox.warning(self, "Aviso", "Selecione um status para atualizar.")
            return
        os_item = self.os_data[idx]
        try:
            update_status_os(os_item["id"], novo_status)
            QMessageBox.information(self, "Sucesso", f"Status da OS {os_item['os']} atualizado para '{novo_status}'.")
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao atualizar status: {e}")

    def refresh(self):
        self._load_os_combobox()
        # Sempre garantir que a coluna 'Valor' preencha o espaço
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, header.ResizeMode.Stretch) 
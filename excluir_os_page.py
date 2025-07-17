from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QTreeWidget, QTreeWidgetItem, QMessageBox
from .dialogs import AutocompleteComboBox
from ..backend.storage_db import get_os_cadastros, delete_os
import os
from PyQt6.QtCore import Qt

class ExcluirOSPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # Carrega registros e mapeamento
        self.registros = get_os_cadastros()
        self.os_map = {str(r['os']): r for r in self.registros}

        # AutoComplete para seleção
        self.combo = AutocompleteComboBox()
        icon_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "imagens", "seta.png"
        ))
        icon_url = icon_path.replace("\\", "/")
        self.combo.setStyleSheet(f"""
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
        self.combo.addItems(list(self.os_map.keys()))
        self.combo.currentTextChanged.connect(self._load_os)
        layout.addWidget(self.combo)

        # Árvore de detalhes
        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Campo", "Valor"])
        self.tree.setStyleSheet("QTreeWidget::item { border-bottom: 1px solid #3a6ea5; }")
        layout.addWidget(self.tree)

        # Botão para excluir
        self.btn_excluir = QPushButton("Excluir OS")
        self.btn_excluir.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.btn_excluir)
        self.btn_excluir.clicked.connect(self._excluir)

    def _formatar_nome_campo(self, campo):
        # Troca _ por espaço e coloca a primeira letra maiúscula de cada palavra
        return str(campo).replace('_', ' ').title() + ":"

    def _load_os(self, os_number: str):
        record = self.os_map.get(os_number)
        self.tree.clear()
        if record:
            for key, val in record.items():
                item = QTreeWidgetItem(self.tree, [self._formatar_nome_campo(key), str(val)])
                font = item.font(0)
                font.setBold(True)
                item.setFont(0, font)

    def _excluir(self):
        os_number = self.combo.currentText()
        confirm = QMessageBox.question(
            self, "Confirmar exclusão",
            f"Deseja realmente excluir a OS {os_number}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            delete_os(os_number)
            QMessageBox.information(self, 'Sucesso', f'OS {os_number} excluída.')

            # Remove do mapeamento e atualiza combo
            self.os_map.pop(os_number, None)
            self.combo.clear()
            self.combo.addItems(list(self.os_map.keys()))
            self.tree.clear()
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Falha ao excluir OS:\n{e}')

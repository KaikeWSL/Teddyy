# main/frontend/dialogs.py

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit,
    QDialogButtonBox, QComboBox, QCompleter
)
from PyQt6.QtCore import Qt, QStringListModel
import os


class AskStringDialog(QDialog):
    """
    Diálogo simples para pedir uma string ao usuário,
    com opção de ocultar entrada (para senhas).
    """
    def __init__(self, parent=None, title: str = "", prompt: str = "", echo_mode: QLineEdit.EchoMode = QLineEdit.EchoMode.Normal):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.result_text: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.addWidget(QLabel(prompt, self))

        self.line_edit = QLineEdit(self)
        self.line_edit.setEchoMode(echo_mode)
        layout.addWidget(self.line_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, Qt.Orientation.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:
        self.result_text = self.line_edit.text()
        super().accept()

    def get_result(self) -> str:
        return self.result_text


def ask_string(parent, title: str, prompt: str, password: bool = False) -> str | None:
    """
    Abre AskStringDialog e retorna a string digitada ou None se cancelado.
    """
    dlg = AskStringDialog(parent, title, prompt,
                          echo_mode=QLineEdit.EchoMode.Password if password else QLineEdit.EchoMode.Normal)
    if dlg.exec() == QDialog.DialogCode.Accepted:
        return dlg.get_result()
    return None


class AutocompleteComboBox(QComboBox):
    """
    QComboBox com autocompletar baseado em QCompleter e lista fornecida.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setEditable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._completer = QCompleter(self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setCompleter(self._completer)
        icon_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "imagens", "seta.png"
        ))
        icon_url = icon_path.replace("\\", "/")
        self.setStyleSheet(f"""
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

    def set_completion_list(self, items: list[str]):
        """
        Recebe lista de strings, define os valores e o modelo do completer.
        """
        self.clear()
        self.addItems(items)
        model = QStringListModel(items, self._completer)
        self._completer.setModel(model)

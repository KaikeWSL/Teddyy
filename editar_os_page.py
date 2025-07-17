from pickle import FRAME
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QFormLayout, QLineEdit, QTextEdit, QMessageBox,QToolButton,QCalendarWidget, QGroupBox
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, QDate,QSize
from main.backend import storage_db

from main.backend.format_utils import format_brl, parse_currency
import os
class CampoDataCustom(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.line = QLineEdit()
        self.line.setPlaceholderText("")
        self.line.setReadOnly(True)
        self.btn = QToolButton()
        self.btn.setText("")
        icon_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "imagens", "data.png"
        ))
        self.btn.setIcon(QIcon(icon_path))
        self.btn.setIconSize(QSize(40, 40))
        self.btn.setStyleSheet("""
            QToolButton {
                border: none;
                background: transparent;

            }
            QToolButton:hover {
                background: rgba(0, 0, 0, 0.1);
                border-radius: 2px;
            }
        """)
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.setFixedWidth(46)
        self.btn.clicked.connect(self.mostrar_calendario)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        layout.addWidget(self.line)
        layout.addWidget(self.btn)
        self.cal = QCalendarWidget()
        self.cal.setWindowFlags(self.cal.windowFlags() | Qt.WindowType.Popup)
        self.cal.clicked.connect(self.selecionar_data)

    def mostrar_calendario(self):
        btn_pos = self.btn.mapToGlobal(self.btn.rect().bottomLeft())
        cal_height = self.cal.sizeHint().height()
        screen = self.cal.screen().geometry()
        # Se não couber para baixo, abre para cima
        if btn_pos.y() + cal_height > screen.bottom():
            pos = self.btn.mapToGlobal(self.btn.rect().topLeft())
            pos.setY(pos.y() - cal_height)
            self.cal.move(pos)
        else:
            self.cal.move(btn_pos)
        self.cal.show()

    def selecionar_data(self, qdate: QDate):
        self.line.setText(qdate.toString("dd/MM/yyyy"))
        self.cal.hide()

    def text(self):
        return self.line.text()

    def setText(self, value):
        self.line.setText(value)

    def clear(self):
        self.line.clear()

    def date(self):
        try:
            return QDate.fromString(self.line.text(), "dd/MM/yyyy")
        except Exception:
            return QDate()
class EditarOSPage(QWidget):
    CAMPOS = [
        "Cliente", "Modelo", "OS", "Entrada equip.", "Valor", "Saída equip.", "Pagamento",
        "Data pagamento 1", "Data pagamento 2", "Data pagamento 3", "N° Serie", "Técnico",
        "Vezes", "Avaliacao tecnica", "Causa provavel"
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar OS")
        self.resize(1100, 400)
        self.os_data = []
        self.current_os = None
        self.entries = {}
        self._setup_ui()
        self._load_os_list()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        # Linha de seleção
        hbox = QHBoxLayout()
        hbox.addWidget(QLabel("Selecione a OS:"))
        self.combo_os = QComboBox()
        self.combo_os.setEditable(True)
        self.combo_os.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.combo_os.setMinimumWidth(200)
        self.combo_os.currentTextChanged.connect(self._on_os_selected)
        icon_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "imagens", "seta.png"
        ))
        icon_url = icon_path.replace("\\", "/")
        self.combo_os.setStyleSheet(f"""
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
        hbox.addWidget(self.combo_os)
        layout.addLayout(hbox)

        # --- Grupo de edição igual ao cadastro ---
        altura_fixa = 38
        gb = QGroupBox("EDITAR OS")
        gb.setMinimumHeight(altura_fixa * 13 + 60)
        from PyQt6.QtWidgets import QSizePolicy
        gb.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed))
        self.form = QFormLayout()
        self.form.setVerticalSpacing(14)
        self.form.setHorizontalSpacing(8)
        self.form.setContentsMargins(10, 10, 10, 10)
        gb.setLayout(self.form)

        # Campos
        self.entries["OS"] = QLineEdit()
        self.entries["Cliente"] = QLineEdit()
        self.entries["Modelo"] = QLineEdit()
        self.entries["Entrada equip."] = CampoDataCustom()
        self.entries["Valor"] = QLineEdit()
        self.entries["Valor"].editingFinished.connect(lambda: self.entries["Valor"].setText(format_brl(self.entries["Valor"].text())))
        self.entries["Saída equip."] = CampoDataCustom()
        self.entries["Pagamento"] = QLineEdit()
        self.entries["Pagamento"].editingFinished.connect(lambda: self.entries["Pagamento"].setText(format_brl(self.entries["Pagamento"].text())))
        self.entries["Vezes"] = QLineEdit()
        for i in range(1, 4):
            self.entries[f"Data pagamento {i}"] = CampoDataCustom()
        self.entries["N° Serie"] = QLineEdit()
        self.entries["Técnico"] = QLineEdit()
        self.entries["Avaliacao tecnica"] = QTextEdit()
        self.entries["Causa provavel"] = QTextEdit()

        # Ajusta altura dos campos
        for campo, widget in self.entries.items():
            if isinstance(widget, QLineEdit):
                widget.setMinimumHeight(altura_fixa)
                widget.setMaximumHeight(altura_fixa)
            elif isinstance(widget, CampoDataCustom):
                widget.setMinimumHeight(altura_fixa)
                widget.setMaximumHeight(altura_fixa)
                widget.line.setMinimumHeight(altura_fixa)
                widget.line.setMaximumHeight(altura_fixa)

        # Adiciona ao formulário
        self.form.addRow("OS:", self.entries["OS"])
        self.form.addRow("Cliente:", self.entries["Cliente"])
        self.form.addRow("Modelo:", self.entries["Modelo"])
        self.form.addRow("Entrada equip.:", self.entries["Entrada equip."])
        self.form.addRow("Valor:", self.entries["Valor"])
        self.form.addRow("Saída equip.:", self.entries["Saída equip."])
        self.form.addRow("Pagamento:", self.entries["Pagamento"])
        self.form.addRow("Vezes:", self.entries["Vezes"])
        self.form.addRow("Data pagamento 1:", self.entries["Data pagamento 1"])
        self.form.addRow("Data pagamento 2:", self.entries["Data pagamento 2"])
        self.form.addRow("Data pagamento 3:", self.entries["Data pagamento 3"])
        self.form.addRow("N° Serie:", self.entries["N° Serie"])
        self.form.addRow("Técnico:", self.entries["Técnico"])


        # --- Layout principal: formulário à esquerda, avaliação/causa à direita ---
        main_hbox = QHBoxLayout()
        # Formulário de edição (esquerda)
        main_hbox.addWidget(gb, 2)      # Esquerda maior

        # Coluna direita: Avaliação técnica e Causa provável
        right = QVBoxLayout()
        gb1 = QGroupBox("AVALIAÇÃO TÉCNICA")
        te1 = self.entries["Avaliacao tecnica"]
        layout1 = QVBoxLayout()
        gb1.setLayout(layout1)
        layout1.addWidget(te1)
        right.addWidget(gb1)

        gb2 = QGroupBox("CAUSA PROVÁVEL")
        te2 = self.entries["Causa provavel"]
        layout2 = QVBoxLayout()
        gb2.setLayout(layout2)
        layout2.addWidget(te2)
        right.addWidget(gb2)
        right.addStretch()

        main_hbox.addLayout(right, 1)   # Direita menor
        layout.addLayout(main_hbox)

        # Botão atualizar
        self.btn_atualizar = QPushButton("Atualizar OS")
        self.btn_atualizar.clicked.connect(self._atualizar_os)
        layout.addWidget(self.btn_atualizar)

    def _load_os_list(self):
        self.os_data = storage_db.get_os_cadastros()
        os_numeros = sorted({str(os["os"]) for os in self.os_data if "os" in os})
        self.combo_os.clear()
        self.combo_os.addItems(os_numeros)

    def _on_os_selected(self, os_numero):
        os_numero = os_numero.strip()
        if not os_numero:
            for campo, widget in self.entries.items():
                if isinstance(widget, (QLineEdit, CampoDataCustom)):
                    widget.clear()
                elif isinstance(widget, QTextEdit):
                    widget.clear()
            self.current_os = None
            return
        # Busca a OS selecionada
        for os in self.os_data:
            if str(os.get("os", "")) == os_numero:
                self.current_os = os
                break
        else:
            self.current_os = None
        self._preencher_campos()

    def _preencher_campos(self):
        if not self.current_os:
            for campo, widget in self.entries.items():
                if isinstance(widget, (QLineEdit, CampoDataCustom)):
                    widget.clear()
                elif isinstance(widget, QTextEdit):
                    widget.clear()
            return
        os = self.current_os
        self.entries["OS"].setText(str(os.get("os", "")))
        self.entries["Cliente"].setText(str(os.get("cliente", "")))
        self.entries["Modelo"].setText(str(os.get("modelo", "")))
        self.entries["Entrada equip."].setText(str(os.get("entrada_equip", "")))
        self.entries["Valor"].setText(format_brl(os.get("valor", "")))
        self.entries["Saída equip."].setText(str(os.get("saida_equip", "")))
        self.entries["Pagamento"].setText(format_brl(os.get("pagamento", "")))
        self.entries["Vezes"].setText(str(os.get("vezes", "")))
        self.entries["Data pagamento 1"].setText(str(os.get("data_pag1", "")))
        self.entries["Data pagamento 2"].setText(str(os.get("data_pag2", "")))
        self.entries["Data pagamento 3"].setText(str(os.get("data_pag3", "")))
        self.entries["N° Serie"].setText(str(os.get("serie", "")))
        self.entries["Técnico"].setText(str(os.get("tecnico", "")))
        self.entries["Avaliacao tecnica"].setPlainText(str(os.get("avaliacao_tecnica", "")))
        self.entries["Causa provavel"].setPlainText(str(os.get("causa_provavel", "")))

    def _atualizar_os(self):
        if not self.current_os:
            QMessageBox.warning(self, "Atenção", "Selecione uma OS para editar.")
            return
        # Coleta os dados dos campos
        dados = dict(self.current_os)
        dados['os'] = self.entries["OS"].text().strip()
        dados['cliente'] = self.entries["Cliente"].text().strip()
        dados['modelo'] = self.entries["Modelo"].text().strip()
        dados['entrada_equip'] = self.entries["Entrada equip."].text().strip()
        dados['valor'] = self.entries["Valor"].text().strip()
        dados['saida_equip'] = self.entries["Saída equip."].text().strip()
        dados['pagamento'] = self.entries["Pagamento"].text().strip()
        dados['vezes'] = self.entries["Vezes"].text().strip()
        dados['data_pag1'] = self.entries["Data pagamento 1"].text().strip()
        dados['data_pag2'] = self.entries["Data pagamento 2"].text().strip()
        dados['data_pag3'] = self.entries["Data pagamento 3"].text().strip()
        dados['serie'] = self.entries["N° Serie"].text().strip()
        dados['tecnico'] = self.entries["Técnico"].text().strip()
        dados['avaliacao_tecnica'] = self.entries["Avaliacao tecnica"].toPlainText().strip()
        dados['causa_provavel'] = self.entries["Causa provavel"].toPlainText().strip()
        try:
            storage_db.insert_os(
                id=dados.get("id"),
                os=dados.get("os", ""),
                cliente=dados.get("cliente", ""),
                modelo=dados.get("modelo", ""),
                entrada_equip=dados.get("entrada_equip", ""),
                valor=dados.get("valor", ""),
                saida_equip=dados.get("saida_equip", ""),
                pagamento=dados.get("pagamento", ""),
                vezes=dados.get("vezes", ""),
                data_pag1=dados.get("data_pag1", ""),
                data_pag2=dados.get("data_pag2", ""),
                data_pag3=dados.get("data_pag3", ""),
                serie=dados.get("serie", ""),
                tecnico=dados.get("tecnico", ""),
                status=dados.get("status", ""),
                avaliacao_tecnica=dados.get("avaliacao_tecnica", ""),
                causa_provavel=dados.get("causa_provavel", "")
            )
            QMessageBox.information(self, "Sucesso", "OS atualizada com sucesso!")
            self._load_os_list()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao atualizar OS: {e}")

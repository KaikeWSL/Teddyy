from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QPushButton, QMessageBox, QScrollArea,QSizePolicy, QFrame
)

from .dialogs import AutocompleteComboBox
from ..backend.storage_db import get_os_cadastros
import pandas as pd
import os
import subprocess


class AbrirOSPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)

        # 1) Buscar registros de OS no banco
        registros = get_os_cadastros()
        df = pd.DataFrame(registros)

        # 2) ComboBox de seleção de OS + botão "Visualizar"
        top_row = QHBoxLayout()
        self.combo = AutocompleteComboBox()
        self.combo.setPlaceholderText("Selecione a OS...")
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
        top_row.addWidget(self.combo, stretch=3)
        self.btn_visualizar = QPushButton("Visualizar")
        self.btn_visualizar.clicked.connect(self._on_visualizar_clicked)
        top_row.addWidget(self.btn_visualizar, stretch=1)
        main_layout.addLayout(top_row)

        # 3) Grupo "Detalhes da OS" (substitui a tabela)
        self.details_group = QGroupBox("Detalhes da OS")

        self.details_layout = QFormLayout(self.details_group)
        self.details_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        details_scroll = QScrollArea()
        details_scroll.setWidgetResizable(True)
        details_scroll.setWidget(self.details_group)

        main_layout.addWidget(details_scroll, stretch=1)

        # 4) Container para botões de arquivo (Excel à esquerda, PDF à direita)
        files_container = QWidget()
        file_layout = QHBoxLayout(files_container)

        # 4.1) Grupo "Excel"
        self.excel_group = QGroupBox("Excel")
        self.excel_group.setMaximumHeight(150)
        self.excel_layout = QVBoxLayout(self.excel_group)
        excel_scroll = QScrollArea()
        excel_scroll.setWidgetResizable(True)
        excel_scroll.setWidget(self.excel_group)
        excel_scroll.setMaximumHeight(150)

        # 4.2) Grupo "PDF"
        self.pdf_group = QGroupBox("PDF")
        self.pdf_group.setMaximumHeight(150)
        self.pdf_layout = QVBoxLayout(self.pdf_group)
        pdf_scroll = QScrollArea()
        pdf_scroll.setWidgetResizable(True)
        pdf_scroll.setWidget(self.pdf_group)
        pdf_scroll.setMaximumHeight(150)

        file_layout.addWidget(excel_scroll, stretch=1)
        file_layout.addWidget(pdf_scroll, stretch=1)
        main_layout.addWidget(files_container, stretch=2)

        # 5) Detectar o cargo do usuário (supõe-se parent.cargo)
        if parent is not None and hasattr(parent, 'cargo'):
            self.cargo = parent.cargo.lower()
        else:
            self.cargo = "ceo"  # assume acesso total

        # 6) Preencher a combo com todos os números de OS
        self.combo.addItems(df['os'].astype(str).tolist())

    def _formatar_nome_campo(self, campo):
        # Troca _ por espaço e coloca a primeira letra maiúscula de cada palavra
        return str(campo).replace('_', ' ').title() + ":"

    def _on_visualizar_clicked(self):
        """
        Chamado quando o usuário clica em "Visualizar":
        carrega detalhes e botões para a OS selecionada.
        """
        os_number = self.combo.currentText().strip()
        if not os_number:
            QMessageBox.warning(None, "Aviso", "Selecione uma OS antes de visualizar.")
            return
        self._on_os_changed(os_number)

    def _on_os_changed(self, os_number: str):
        """
        Atualiza o grupo de detalhes e os botões de arquivo conforme a OS selecionada.
        """
        # Limpar detalhes atuais
        while self.details_layout.rowCount() > 0:
            self.details_layout.removeRow(0)

        # Buscar novamente dados no banco
        registros = get_os_cadastros()
        df = pd.DataFrame(registros)
        rec = df[df['os'].astype(str) == os_number]

        if rec.empty:
            QMessageBox.warning(None, "Aviso", f"OS {os_number} não encontrada.")
            # Limpa também botões
            self._clear_file_buttons()
            return

        # Pegar o primeiro (único) registro
        row = rec.iloc[0]

        # Adicionar cada coluna ao FormLayout: "rótulo: valor"
        for col in df.columns:
            valor = row[col]
            if pd.isna(valor):
                valor = ""
            label_key = QLabel(self._formatar_nome_campo(col))
            font = label_key.font()
            font.setBold(True)
            label_key.setFont(font)
            label_val = QLabel(str(valor))
            label_val.setWordWrap(True)
            self.details_layout.addRow(label_key, label_val)
            # Adiciona divisória
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setFrameShadow(QFrame.Shadow.Sunken)
            line.setStyleSheet("color: #3a6ea5; background: #3a6ea5; min-height: 1px; max-height: 1px;")
            self.details_layout.addRow(line)

        # Reconstruir botões de arquivo (Excel e PDF)
        self._rebuild_file_buttons(os_number, row.get('cliente', ""))

    def _clear_file_buttons(self):
        """
        Remove todos os botões atuais de Excel e PDF (usado para limpar se OS não existir).
        """
        for i in reversed(range(self.excel_layout.count())):
            w = self.excel_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        for i in reversed(range(self.pdf_layout.count())):
            w = self.pdf_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

    def _rebuild_file_buttons(self, os_number: str, cliente: str):
        """
        Remove todos os botões atuais e adiciona novos conforme cargo e existência dos arquivos.
        """
        # Limpar botões atuais
        self._clear_file_buttons()

        if not cliente:
            return

        # Pasta onde os arquivos estão: Z:\OS\<Cliente>\<OS>\
        caminho_base = os.path.join(r"Z:\OS", str(cliente), str(os_number))
        if not os.path.isdir(caminho_base):
            QMessageBox.critical(None, "Erro",
                                 f"Pasta não encontrada:\n{caminho_base}")
            return

        # Quais arquivos temos disponíveis no disco
        possíveis = {
            'orçamento.xlsx': 'excel',
            'orçamento_tecnicos.xlsx': 'excel',
            'orçamento.pdf': 'pdf',
            'orçamento_tecnicos.pdf': 'pdf'
        }

        # Definir lista de permitidos por cargo
        if self.cargo in ("ceo", "administrativo"):
            permitidos = list(possíveis.keys())
        elif self.cargo in ("técnico", "tecnico", "gerente"):
            permitidos = ["orçamento_tecnicos.xlsx", "orçamento_tecnicos.pdf"]
        else:
            permitidos = list(possíveis.keys())

        # Para cada arquivo permitido, caso exista, cria um botão
        any_excel = False
        any_pdf = False
        for nome_arquivo in permitidos:
            full_path = os.path.join(caminho_base, nome_arquivo)
            if os.path.isfile(full_path):
                tipo = possíveis[nome_arquivo]
                btn = QPushButton(nome_arquivo)
                btn.clicked.connect(lambda _, p=full_path: self._open_file(p))
                if tipo == 'excel':
                    self.excel_layout.addWidget(btn)
                    any_excel = True
                else:
                    self.pdf_layout.addWidget(btn)
                    any_pdf = True

        # Se nenhum .xlsx foi adicionado, exibir um aviso na categoria Excel
        if not any_excel:
            label = QLabel("Nenhum .xlsx disponível.")
            self.excel_layout.addWidget(label)

        # Se nenhum .pdf foi adicionado, exibir aviso na categoria PDF
        if not any_pdf:
            label = QLabel("Nenhum .pdf disponível.")
            self.pdf_layout.addWidget(label)

    def _open_file(self, path: str):
        """
        Abre o arquivo no aplicativo padrão do Windows.
        """
        try:
            os.startfile(path)
        except Exception:
            try:
                subprocess.Popen([path], shell=True)
            except Exception as e:
                QMessageBox.critical(None, "Erro",
                                     f"Não foi possível abrir o arquivo:\n{e}")

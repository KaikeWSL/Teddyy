from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QLineEdit, QPushButton, QTableView, QDialog, QDialogButtonBox, QFormLayout
)
from PyQt6.QtCore import Qt
import pandas as pd
import os

from .dialogs import AutocompleteComboBox
from ..backend.storage_db import get_table_normalized, update_status_os
from .pandas_model import PandasModel


class StatusDelegate(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.addItems([
            "Orçamento",
            "Aguardando aprovação",
            "Aprovado",
            "Em manutenção",
            "Manutenção em andamento",
            "Manutenção finalizada",
            "Aguardando entrega",
            "Entregue"
        ])
        self.setEditable(False)

from PyQt6.QtWidgets import QStyledItemDelegate
class StatusEditDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        return StatusDelegate(parent)
    def setEditorData(self, editor, index):
        value = index.model().data(index, Qt.ItemDataRole.EditRole)
        idx = editor.findText(value)
        if idx >= 0:
            editor.setCurrentIndex(idx)
    def setModelData(self, editor, model, index):
        value = editor.currentText()
        model.setData(index, value, Qt.ItemDataRole.EditRole)
        # Atualiza no banco
        os_id = model._df.iloc[index.row()]['id']
        update_status_os(os_id, value)


class FiltrosDialog(QDialog):
    def __init__(self, parent, df, status_options):
        super().__init__(parent)
        self.setWindowTitle("Filtros do Resumo")
        self.df = df
        self.status_options = status_options
        self.result = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.inputs = {}
        # Filtros principais
        for label, attr in [
            ("Cliente", 'cliente'),
            ("Modelo", 'modelo'),
            ("OS", 'os'),
            ("Série", 'serie'),
            ("Técnico", 'tecnico'),
        ]:
            cb = AutocompleteComboBox()
            cb.addItem("Todos", "")
            values = self.df[attr].dropna().unique()
            values = [str(v) for v in values if v is not None and str(v).strip() != ""]
            for v in sorted(values):
                cb.addItem(v, v)
            form.addRow(label+':', cb)
            self.inputs[attr] = cb
        # Status
        icon_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "imagens", "seta.png"
        ))
        icon_url = icon_path.replace("\\", "/")
        cb_status = QComboBox()
        cb_status.setStyleSheet(f"""
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
        cb_status.addItem("Todos", "")
        for status in self.status_options:
            cb_status.addItem(status, status)
        form.addRow("Status:", cb_status)
        self.inputs['status'] = cb_status
        # Mês de Entrada
        cb_month = QComboBox()
        cb_month.setStyleSheet(f"""
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
        cb_month.addItem("Todos meses", None)
        meses = [("Jan",1),("Fev",2),("Mar",3),("Abr",4),("Mai",5),("Jun",6),
                 ("Jul",7),("Ago",8),("Set",9),("Out",10),("Nov",11),("Dez",12)]
        for nome, num in meses:
            cb_month.addItem(nome, num)
        form.addRow("Mês de Entrada:", cb_month)
        self.inputs['month'] = cb_month
        # Ano de Entrada
        cb_year = QComboBox()
        cb_year.setStyleSheet(f"""
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
        cb_year.addItem("Todos anos", None)
        anos = sorted(self.df['entrada_equip'].dt.year.dropna().unique())
        for ano in anos:
            if pd.notna(ano):
                cb_year.addItem(str(int(ano)), int(ano))
        form.addRow("Ano de Entrada:", cb_year)
        self.inputs['year'] = cb_year
        # Mês de Saída
        cb_month_saida = QComboBox()
        cb_month_saida.setStyleSheet(cb_month.styleSheet())
        cb_month_saida.addItem("Todos meses", None)
        for nome, num in meses:
            cb_month_saida.addItem(nome, num)
        form.addRow("Mês de Saída:", cb_month_saida)
        self.inputs['month_saida'] = cb_month_saida
        # Ano de Saída
        cb_year_saida = QComboBox()
        cb_year_saida.setStyleSheet(cb_year.styleSheet())
        cb_year_saida.addItem("Todos anos", None)
        if 'saida_equip' in self.df.columns:
            anos_saida = sorted(self.df['saida_equip'].dropna().astype(str).apply(lambda x: pd.to_datetime(x, errors='coerce').year).dropna().unique())
            for ano in anos_saida:
                if pd.notna(ano):
                    cb_year_saida.addItem(str(int(ano)), int(ano))
        form.addRow("Ano de Saída:", cb_year_saida)
        self.inputs['year_saida'] = cb_year_saida
        # Texto livre
        le_text = QLineEdit()
        le_text.setPlaceholderText("Texto livre")
        le_text.setClearButtonEnabled(True)
        form.addRow("Texto livre:", le_text)
        self.inputs['text'] = le_text
        layout.addLayout(form)
        # Botões
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Reset | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(self._reset)
        layout.addWidget(btns)

    def get_filters(self):
        filtros = {}
        for attr, widget in self.inputs.items():
            if isinstance(widget, QComboBox):
                idx = widget.currentIndex()
                val = widget.itemData(idx)
                # Só filtra se não for vazio e não for 'Todos'
                if val is not None and val != '':
                    filtros[attr] = val
            else:
                val = widget.text().strip()
                if val:
                    filtros[attr] = val
        return filtros

    def _reset(self):
        for attr, widget in self.inputs.items():
            if isinstance(widget, QComboBox):
                widget.setCurrentIndex(0)
            else:
                widget.clear()

class Resumo(QWidget):
    DATE_COLUMN = "entrada_equip"
    FILTER_ATTRIBUTES = ['cliente', 'modelo', 'os', 'serie', 'tecnico', 'status']    
    STATUS_OPTIONS = [
        "Orçamento",
        "Aguardando aprovação",
        "Aprovado",
        "Em manutenção",
        "Manutenção em andamento",
        "Manutenção finalizada",
        "Aguardando entrega",
        "Entregue"
    ]

    def __init__(self):
        super().__init__()
        try:
            records = get_table_normalized('os_cadastros')
            self.df = pd.DataFrame(records)
            self.df.drop(columns=['id'], inplace=True, errors='ignore')
            # NOVO: Mostra valores originais para debug

            # Converte datas manualmente, múltiplos formatos
            self.df[self.DATE_COLUMN] = self.df[self.DATE_COLUMN].astype(str).apply(self.try_parse_date)

            # Converte strings para category para filtros eficientes
            for col in self.FILTER_ATTRIBUTES:
                self.df[col] = self.df[col].astype('category')
            self.filtros = {}
            self._build_ui()
            self._apply_filter()
        except Exception as e:
            print(f"Erro ao carregar o Resumo: {str(e)}")
            raise

    def try_parse_date(self, val):
        """Tenta converter para datetime com formatos brasileiros e ISO."""
        if pd.isna(val) or val in ['', None, 'NIL', 'NONE']:
            return pd.NaT
        val = str(val).strip()
        if not val or val.lower() in ['nan', 'nat']:
            return pd.NaT
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d", "%d.%m.%Y"):
            try:
                return pd.to_datetime(val, format=fmt)
            except Exception:
                continue
        # Última tentativa: conversão automática do pandas
        try:
            return pd.to_datetime(val, errors='coerce')
        except Exception:
            return pd.NaT

    def _build_ui(self):
        lay = QVBoxLayout(self)
        # Botão de filtros
        h1 = QHBoxLayout()
        btn_filtros = QPushButton("Filtros")
        btn_filtros.clicked.connect(self._abrir_filtros)
        h1.addWidget(btn_filtros)
        lay.addLayout(h1)
        # Tabela
        self.table = QTableView()
        self.table.setItemDelegateForColumn(self.df.columns.get_loc('status'), StatusEditDelegate(self.table))
        lay.addWidget(self.table, 1)
        self.model = PandasModel(self.df)
        self.table.setModel(self.model)
        # Ajustar a coluna 'valor' para preencher o espaço
        header = self.table.horizontalHeader()
        # Ajustar larguras customizadas
        colunas_largura = {
            'cliente': 230,
            'modelo': 120,
            'os': 70,
            'entrada_equip': 110,
            'valor': 100,
            'saida_equip': 110,
            'pagamento': 100,
            'data_pag1': 150,
            'data_pag2': 150,
            'data_pag3': 150,
            'serie': 100,
            'tecnico': 120,
            'vezes': 70,
            'avaliacao_tecnica': 220,
            'causa_provavel': 220,
            'status': 200
        }
        for nome, largura in colunas_largura.items():
            if nome in self.df.columns:
                idx = self.df.columns.get_loc(nome)
                header.setSectionResizeMode(idx, header.ResizeMode.Interactive)
                header.resizeSection(idx, largura)
        if 'valor' in self.df.columns:
            idx = self.df.columns.get_loc('valor')
            header.setSectionResizeMode(idx, header.ResizeMode.Stretch)
        # Label de contagem
        self.lbl_count = QLabel()
        lay.addWidget(self.lbl_count)

    def _abrir_filtros(self):
        dlg = FiltrosDialog(self, self.df, self.STATUS_OPTIONS)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.filtros = dlg.get_filters()
            self._apply_filter()

    def _apply_filter(self):
        try:
            df = self.df
            masks = []
            filtros = self.filtros if hasattr(self, 'filtros') else {}
            # Filtros por atributo
            for attr in self.FILTER_ATTRIBUTES:
                if attr in filtros and filtros[attr] != '':
                    if attr == 'status':
                        masks.append(df[attr] == filtros[attr])
                    else:
                        masks.append(df[attr].astype(str).str.contains(str(filtros[attr]), case=False, na=False))
            # Filtro texto livre
            txt = filtros.get('text', '').strip().lower() if filtros else ''
            if txt:
                text_mask = df[self.FILTER_ATTRIBUTES].astype(str).apply(
                    lambda x: x.str.lower().str.contains(txt, na=False)
                ).any(axis=1)
                masks.append(text_mask)
            # Filtro por data de entrada
            m = filtros.get('month', None)
            y = filtros.get('year', None)
            if m is not None and m != '':
                masks.append(df[self.DATE_COLUMN].dt.month == int(m))
            if y is not None and y != '':
                masks.append(df[self.DATE_COLUMN].dt.year == int(y))
            # Filtro por data de saída
            m_saida = filtros.get('month_saida', None)
            y_saida = filtros.get('year_saida', None)
            if 'saida_equip' in df.columns:
                saida_col = df['saida_equip'].astype(str).apply(lambda x: pd.to_datetime(x, errors='coerce'))
                if m_saida is not None and m_saida != '':
                    masks.append(saida_col.dt.month == int(m_saida))
                if y_saida is not None and y_saida != '':
                    masks.append(saida_col.dt.year == int(y_saida))
            final_mask = pd.Series(True, index=df.index)
            if masks:
                final_mask = pd.concat(masks, axis=1).all(axis=1)
            filtered = df[final_mask]
            self.model.setDataFrame(filtered)
            self.table.scrollToTop()
            self.lbl_count.setText(f"Registros: {len(filtered)}")
        except Exception as e:
            print(f"Error applying filter: {str(e)}")

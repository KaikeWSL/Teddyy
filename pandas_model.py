import locale
import pandas as pd
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QVariant
from PyQt6.QtGui import QColor
from datetime import datetime
import re

try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'Portuguese_Brazil.1252')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, 'Portuguese_Brazil')
        except locale.Error:
            print("Aviso: Não foi possível configurar locale para português brasileiro")

class PandasModel(QAbstractTableModel):
    def __init__(self, df):
        super().__init__()
        self._df = df.copy()
        self._currency_columns = []

    def rowCount(self, parent=QModelIndex()):
        return len(self._df)

    def columnCount(self, parent=QModelIndex()):
        return len(self._df.columns)

    def _is_date_column(self, col_name):
        col_lower = col_name.lower()
        return any(keyword in col_lower for keyword in ['data', 'date', 'entrada_equip'])

    def _is_currency_column(self, col_name):
        if col_name in self._currency_columns:
            return True
        col_lower = col_name.lower()
        return any(keyword in col_lower for keyword in ['valor', 'pagamento', 'preco', 'price', 'amount'])

    def _parse_date(self, value):
        if pd.isna(value) or value in ['', None, 'NIL', 'NONE']:
            return None
        if isinstance(value, pd.Timestamp):
            return value
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            date_formats = [
                '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y',
                '%d/%m/%y', '%d-%m-%y', '%d.%m.%Y',
                '%d.%m.%y', '%Y/%m/%d', '%Y.%m.%d'
            ]
            for fmt in date_formats:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
        if isinstance(value, (int, float)):
            try:
                return pd.to_datetime(value, unit='s')
            except:
                try:
                    return pd.to_datetime(value, unit='ms')
                except:
                    pass
        return None

    def _format_currency(self, value):
        if pd.isna(value) or value in ['', None, 'NIL', 'NONE']:
            return ''
        try:
            if isinstance(value, str):
                clean_value = re.sub(r'[^\d,.-]', '', value)
                if ',' in clean_value:
                    clean_value = clean_value.replace('.', '').replace(',', '.')
                value = float(clean_value)
            try:
                return locale.currency(value, grouping=True)
            except:
                formatted = f"{abs(value):,.2f}"
                formatted = formatted.replace(',', 'X').replace('.', ',').replace('X', '.')
                prefix = 'R$ ' if value >= 0 else '-R$ '
                return prefix + formatted
        except (ValueError, TypeError):
            return str(value)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return QVariant()
        value = self._df.iat[index.row(), index.column()]
        col_name = self._df.columns[index.column()]
        # Removido print de debug de entrada_equip
        # if col_name == "entrada_equip":
        #     print(f"DEBUG: entrada_equip linha {index.row()}: {repr(value)}")
        if role == Qt.ItemDataRole.DisplayRole:
            # Formatação de data
            if self._is_date_column(col_name):
                parsed_date = self._parse_date(value)
                if parsed_date:
                    return parsed_date.strftime('%d/%m/%Y')
                else:
                    return ''
            # Para todas as outras colunas, exibe exatamente como veio do banco
            return '' if pd.isna(value) or value in [None, '', 'NIL', 'NONE'] else str(value)
        # Para valores negativos de moeda, pode adicionar cor vermelha (opcional)
        if role == Qt.ItemDataRole.ForegroundRole:
            # Regra especial para coluna pagamento
            if col_name.lower() == 'pagamento':
                try:
                    # Busca o valor da mesma linha na coluna 'valor'
                    valor_idx = list(self._df.columns.str.lower()).index('valor')
                    valor_raw = self._df.iat[index.row(), valor_idx]
                    pagamento_raw = value
                    # Converte ambos para float
                    def to_float(val):
                        if pd.isna(val) or val in ['', None, 'NIL', 'NONE']:
                            return 0.0
                        if isinstance(val, str):
                            clean = re.sub(r'[^\d,.-]', '', val)
                            if ',' in clean:
                                clean = clean.replace('.', '').replace(',', '.')
                            return float(clean)
                        return float(val)
                    valor = to_float(valor_raw)
                    pagamento = to_float(pagamento_raw)
                    if pagamento < valor:
                        return QColor(255, 80, 80)  # vermelho claro
                    elif pagamento == valor and valor != 0:
                        return QColor(0, 180, 0)  # verde
                except Exception:
                    pass
            # Regra antiga: moeda negativa
            if self._is_currency_column(col_name):
                try:
                    if isinstance(value, str):
                        clean_value = re.sub(r'[^\d,.-]', '', value)
                        if ',' in clean_value:
                            clean_value = clean_value.replace('.', '').replace(',', '.')
                        value = float(clean_value)
                    if value < 0:
                        return QColor(Qt.GlobalColor.red)
                except Exception:
                    pass
        return QVariant()

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return QVariant()
        if orientation == Qt.Orientation.Horizontal:
            header_labels = [
                'Cliente', 'Modelo', 'OS', 'Entrada equip.', 'Valor', 'Saida equip.',
                'Pagamento', 'Data pagamento 1', 'Data pagamento 2', 'Data pagamento 3',
                'N° Serie', 'Técnico', 'Vezes', 'Avaliação Técnica', 'Causa Provável', 'Status'
            ]
            if section < len(header_labels):
                return header_labels[section]
            else:
                return self._df.columns[section]
        else:
            return str(self._df.index[section])

    def setDataFrame(self, df):
        self.beginResetModel()
        self._df = df.copy()
        self.endResetModel()

    def add_currency_columns(self, columns):
        if isinstance(columns, str):
            columns = [columns]
        for col in columns:
            if col not in self._currency_columns:
                self._currency_columns.append(col)
        self.beginResetModel()
        self.endResetModel()

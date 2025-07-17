from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableView, QPushButton, QHBoxLayout,
    QTableWidgetItem, QDialog, QFormLayout, QLineEdit, QMessageBox,
    QHeaderView
)
from PyQt6.QtCore import Qt, QAbstractTableModel
import pandas as pd
import logging
from ..backend.storage_db import load_equipamentos,save_equipamentos

class PandasModel(QAbstractTableModel):
    def __init__(self, df=pd.DataFrame()):
        super().__init__()
        # Ensure DataFrame has proper dtypes
        self._df = df.astype({
            'Equipamento': str,
            'Tipo': str,
            'Marca': str
        })

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
            
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            value = self._df.iloc[index.row(), index.column()]
            return str(value) if pd.notna(value) else ""
        return None

    def setData(self, index, value, role):
        if role == Qt.ItemDataRole.EditRole:
            try:
                # Validate equipment name is unique when editing first column
                if index.column() == 0 and value.strip():
                    existing = self._df['Equipamento'].str.lower()
                    if value.lower() in existing[existing.index != index.row()].values:
                        raise ValueError("Equipamento já existe")
                
                # Convert empty strings to empty string instead of NaN
                value = value.strip() if value else ""
                self._df.iloc[index.row(), index.column()] = value
                self.dataChanged.emit(index, index)
                return True
            except Exception as e:
                logging.error(f"Error setting data: {e}")
                return False
        return False

    def rowCount(self, parent=None):
        return len(self._df)

    def columnCount(self, parent=None):
        return len(self._df.columns)

    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self._df.columns[section])
            else:
                return str(section + 1)
        return None

    def flags(self, index):
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable

    def setDataFrame(self, df):
        self.beginResetModel()
        self._df = df.astype({
            'Equipamento': str,
            'Tipo': str,
            'Marca': str
        })
        self.endResetModel()

class EquipamentosPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Cria DataFrame
        equipamentos = load_equipamentos()
        df = pd.DataFrame(equipamentos)
        df = df.rename(columns={
            'equipamento': 'Equipamento',
            'tipo': 'Tipo',
            'marca': 'Marca',
        })

        # View + modelo
        self.table = QTableView()
        self.model = PandasModel(df)
        self.table.setModel(self.model)
        
        # Configurações da tabela
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        
        # Habilita edição
        self.table.setEditTriggers(QTableView.EditTrigger.DoubleClicked | 
                                 QTableView.EditTrigger.EditKeyPressed)
        
        # Otimizações de performance
        self.table.setVerticalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        self.table.setAlternatingRowColors(True)
        
        layout.addWidget(self.table, 1)

        # Botões
        btns = QHBoxLayout()
        btn_novo = QPushButton("Novo")
        btn_novo.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_editar = QPushButton("Editar")
        btn_editar.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_salvar = QPushButton("Salvar")
        btn_salvar.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_excluir = QPushButton("Excluir")
        btn_excluir.setCursor(Qt.CursorShape.PointingHandCursor)
        
        btn_novo.clicked.connect(self._novo_equip)
        btn_editar.clicked.connect(self._editar_equip)
        btn_salvar.clicked.connect(self._salvar_alteracoes)
        btn_excluir.clicked.connect(self._excluir_equip)
        
        btns.addWidget(btn_novo)
        btns.addWidget(btn_editar)
        btns.addWidget(btn_salvar)
        btns.addWidget(btn_excluir)
        layout.addLayout(btns)

    def _novo_equip(self):
        """Abre diálogo para criar novo equipamento"""
        try:
            novo = pd.DataFrame([{
                'Equipamento': '',
                'Tipo': '',
                'Marca': ''
            }])
            
            self.model._df = pd.concat([self.model._df, novo], ignore_index=True)
            self.model.layoutChanged.emit()
            
            # Seleciona e edita a nova linha
            row = len(self.model._df) - 1
            index = self.model.index(row, 0)
            self.table.setCurrentIndex(index)
            self.table.edit(index)
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Erro",
                f"Erro ao criar novo equipamento: {str(e)}"
            )
            self.logger.error(f"Erro ao criar equipamento: {str(e)}")

    def _editar_equip(self):
        """Habilita edição da linha selecionada"""
        indexes = self.table.selectedIndexes()
        if not indexes:
            QMessageBox.warning(self, "Seleção", "Selecione um equipamento para editar.")
            return
        self.table.edit(indexes[0])

    def _salvar_alteracoes(self):
        try:
            df = self.model._df
            # Validação correta: não pode haver vazio ou string vazia
            if df['Equipamento'].isnull().any() or (df['Equipamento'].str.strip() == '').any():
                raise ValueError("Equipamento não pode estar vazio")
            # Monta o dicionário no formato correto
            equipamentos = {
                row['Equipamento']: [row['Tipo'], row['Marca']]
                for _, row in df.iterrows()
                if row['Equipamento'].strip() != ''
            }
            save_equipamentos(equipamentos)
            QMessageBox.information(self, "Sucesso", "Dados salvos com sucesso!")
            self.refresh_equipamentos()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao salvar alterações: {str(e)}")
            self.logger.error(f"Erro ao salvar alterações: {str(e)}")

    def _excluir_equip(self):
        indexes = self.table.selectedIndexes()
        if not indexes:
            QMessageBox.warning(self, "Seleção", "Selecione um equipamento para excluir.")
            return
        row = indexes[0].row()
        equip_name = self.model._df.iloc[row]['Equipamento']
        reply = QMessageBox.question(
            self, "Confirmar Exclusão", 
            f"Deseja excluir o equipamento {equip_name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                df = self.model._df
                # Monta o dicionário ignorando o equipamento a ser removido
                equipamentos = {
                    row['Equipamento']: [row['Tipo'], row['Marca']]
                    for idx, row in df.iterrows()
                    if row['Equipamento'].strip() != '' and row['Equipamento'] != equip_name
                }
                save_equipamentos(equipamentos)
                self.refresh_equipamentos()
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao excluir equipamento: {str(e)}")
                self.logger.error(f"Erro ao excluir equipamento: {str(e)}")

    def refresh_equipamentos(self):
        try:
            equipamentos = load_equipamentos()
            df = pd.DataFrame(equipamentos)
            # Remove a coluna 'id' se existir
            if 'id' in df.columns:
                df = df.drop(columns=['id'])
            if not df.empty:
                df = df.rename(columns={
                    'equipamento': 'Equipamento',
                    'tipo': 'Tipo',
                    'marca': 'Marca',
                })
            self.model.setDataFrame(df)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao atualizar dados: {str(e)}")
            self.logger.error(f"Erro ao atualizar dados: {str(e)}")
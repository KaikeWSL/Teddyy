from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QPushButton, QHBoxLayout,
    QTableWidgetItem, QDialog, QFormLayout, QLineEdit, QMessageBox,
    QHeaderView
)
from PyQt6.QtCore import Qt
from ..backend.storage_db import (
    load_clientes, save_clientes, insert_cliente, 
    update_cliente, delete_cliente
)
import logging

class ClienteDialog(QDialog):
    def __init__(self, parent=None, data=None, edit_mode=False):
        super().__init__(parent)
        self.setWindowTitle("Editar Cliente" if edit_mode else "Novo Cliente")
        self.setMinimumWidth(400)
        self.edit_mode = edit_mode
        self.original_data = data.copy() if data else None
        
        form = QFormLayout(self)

        # Initialize input fields
        self.inputs = {
            'nome': QLineEdit(),
            'cpf_cnpj': QLineEdit(),
            'endereco': QLineEdit(),
            'bairro': QLineEdit(),
            'numero': QLineEdit(),
            'email': QLineEdit(),
            'nome_contato': QLineEdit(),
            'tel_contato': QLineEdit()
        }

        # Add fields to form
        labels = {
            'nome': "Nome:",
            'cpf_cnpj': "CPF/CNPJ:",
            'endereco': "Endereço:",
            'bairro': "Bairro:",
            'numero': "Número:",
            'email': "Email:",
            'nome_contato': "Contato:",
            'tel_contato': "Tel. Contato:"
        }

        for key, label in labels.items():
            form.addRow(label, self.inputs[key])

        # Set existing data if provided
        if data:
            for key, value in data.items():
                if key in self.inputs and value is not None:
                    self.inputs[key].setText(str(value))

        # Buttons
        btns = QHBoxLayout()
        btn_save = QPushButton("Salvar")
        btn_cancel = QPushButton("Cancelar")
        btn_save.clicked.connect(self.validate_and_accept)
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_save)
        btns.addWidget(btn_cancel)
        form.addRow(btns)

    def validate_and_accept(self):
        # Basic validation
        nome = self.inputs['nome'].text().strip()
        if not nome:
            QMessageBox.warning(self, "Validação", "Nome é obrigatório!")
            return
        
        # Validação adicional de CPF/CNPJ se necessário
        cpf_cnpj = self.inputs['cpf_cnpj'].text().strip()
        if cpf_cnpj and len(cpf_cnpj) < 11:
            QMessageBox.warning(self, "Validação", "CPF/CNPJ deve ter pelo menos 11 dígitos!")
            return
            
        self.accept()

    def get_data(self):
        data = {}
        for key, widget in self.inputs.items():
            value = widget.text().strip()
            data[key] = value if value else None
        
        # Mantém o ID original se estiver editando
        if self.edit_mode and self.original_data and 'id' in self.original_data:
            data['id'] = self.original_data['id']
            
        return data

class ClientesPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.clientes = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Table setup
        self.table = QTableWidget(0, 8)
        headers = ["Nome", "CPF/CNPJ", "Endereço", "Bairro",
                  "Número", "Email", "Contato", "Tel. Contato"]
        self.table.setHorizontalHeaderLabels(headers)
        
        # Table configuration
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        
        layout.addWidget(self.table, 1)

        # Buttons
        btns = QHBoxLayout()
        self.buttons = {
            'novo': QPushButton("Novo Cliente"),
            'editar': QPushButton("Editar Cliente"),
            'excluir': QPushButton("Excluir Cliente"),
            'atualizar': QPushButton("Atualizar")
        }
        
        self.buttons['novo'].clicked.connect(self._novo_cliente)
        self.buttons['editar'].clicked.connect(self._editar_cliente)
        self.buttons['excluir'].clicked.connect(self._excluir_cliente)
        self.buttons['atualizar'].clicked.connect(self._load_data)

        for btn in self.buttons.values():
            btns.addWidget(btn)
        
        layout.addLayout(btns)

        # Carrega dados iniciais
        self._load_data()

    def _load_data(self):
        """Carrega dados dos clientes do banco de dados."""
        try:
            self.clientes = load_clientes()
            self.table.setRowCount(len(self.clientes))
            
            for row, cliente in enumerate(self.clientes):
                # Garante que cliente é um dict
                if not isinstance(cliente, dict):
                    self.logger.warning(f"Cliente na linha {row} não é um dict: {cliente}")
                    continue
                    
                # Mapeia os dados para as colunas da tabela
                values = [
                    cliente.get("nome", ""),
                    cliente.get("cpf_cnpj", ""),
                    cliente.get("endereco", ""),
                    cliente.get("bairro", ""),
                    cliente.get("numero", ""),
                    cliente.get("email", ""),
                    cliente.get("nome_contato", ""),
                    cliente.get("tel_contato", "")
                ]

                for col, val in enumerate(values):
                    item = QTableWidgetItem(str(val) if val is not None else "")
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.table.setItem(row, col, item)

            self.table.resizeColumnsToContents()
            self.logger.info(f"Carregados {len(self.clientes)} clientes")
            
        except Exception as e:
            self.logger.error(f"Erro ao carregar clientes: {str(e)}")
            QMessageBox.critical(self, "Erro", 
                               f"Erro ao carregar dados dos clientes:\n{str(e)}")
            self.clientes = []

    def _novo_cliente(self):
        """Cria um novo cliente."""
        try:
            dlg = ClienteDialog(self, edit_mode=False)
            if dlg.exec():
                novo_cliente = dlg.get_data()
                
                # Insere no banco de dados
                insert_cliente(novo_cliente)
                
                # Recarrega os dados
                self._load_data()
                
                QMessageBox.information(self, "Sucesso", 
                                      f"Cliente '{novo_cliente['nome']}' criado com sucesso!")
                
        except Exception as e:
            self.logger.error(f"Erro ao criar cliente: {str(e)}")
            QMessageBox.critical(self, "Erro", 
                               f"Erro ao criar cliente:\n{str(e)}")

    def _editar_cliente(self):
        """Edita o cliente selecionado."""
        try:
            row = self.table.currentRow()
            if row < 0:
                QMessageBox.warning(self, "Seleção", 
                                  "Selecione um cliente antes de editar.")
                return
                
            if row >= len(self.clientes):
                QMessageBox.warning(self, "Erro", "Cliente selecionado é inválido.")
                return
                
            cliente_atual = self.clientes[row]
            
            dlg = ClienteDialog(self, data=cliente_atual, edit_mode=True)
            if dlg.exec():
                cliente_atualizado = dlg.get_data()
                
                # Atualiza no banco de dados
                update_cliente(cliente_atual.get('id'), cliente_atualizado)
                
                # Recarrega os dados
                self._load_data()
                
                QMessageBox.information(self, "Sucesso", 
                                      f"Cliente '{cliente_atualizado['nome']}' atualizado com sucesso!")
                
        except Exception as e:
            self.logger.error(f"Erro ao editar cliente: {str(e)}")
            QMessageBox.critical(self, "Erro", 
                               f"Erro ao editar cliente:\n{str(e)}")

    def _excluir_cliente(self):
        """Exclui o cliente selecionado."""
        try:
            row = self.table.currentRow()
            if row < 0:
                QMessageBox.warning(self, "Seleção", 
                                  "Selecione um cliente para excluir.")
                return
                
            if row >= len(self.clientes):
                QMessageBox.warning(self, "Erro", "Cliente selecionado é inválido.")
                return

            cliente = self.clientes[row]
            nome = cliente.get('nome', 'Cliente sem nome')

            reply = QMessageBox.question(
                self, 'Confirmação',
                f'Deseja realmente excluir o cliente "{nome}"?\n\n'
                f'Esta ação não pode ser desfeita.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Remove do banco de dados
                delete_cliente(cliente.get('id'))
                
                # Recarrega os dados
                self._load_data()
                
                QMessageBox.information(self, "Sucesso", 
                                      f"Cliente '{nome}' excluído com sucesso!")
                
        except Exception as e:
            self.logger.error(f"Erro ao excluir cliente: {str(e)}")
            QMessageBox.critical(self, "Erro", 
                               f"Erro ao excluir cliente:\n{str(e)}")

    def get_selected_cliente(self):
        """Retorna o cliente selecionado na tabela."""
        row = self.table.currentRow()
        if row >= 0 and row < len(self.clientes):
            return self.clientes[row]
        return None

    def refresh_data(self):
        """Método público para atualizar os dados."""
        self._load_data()
from PyQt6.QtWidgets import QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout, QFormLayout, QMessageBox, QGroupBox, QSizePolicy
from PyQt6.QtCore import Qt
from main.backend.storage_db import authenticate_user, update_usuario, _hash_password

class ConfiguracoesUsuarioDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Configuração de Senha')
        self.setMinimumSize(600, 400)  # Tela maior e responsiva
        self.setStyleSheet("")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        group = QGroupBox()
        group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        group_layout = QFormLayout()
        group_layout.setContentsMargins(40, 40, 40, 40)  # Espaço interno agradável
        group_layout.setSpacing(20)

        self.le_usuario = QLineEdit()
        self.le_usuario.setPlaceholderText('Usuário')
        self.le_usuario.setMinimumHeight(40)
        group_layout.addRow('Usuário:', self.le_usuario)

        self.le_senha_antiga = QLineEdit()
        self.le_senha_antiga.setPlaceholderText('Senha antiga')
        self.le_senha_antiga.setEchoMode(QLineEdit.EchoMode.Password)
        self.le_senha_antiga.setMinimumHeight(40)
        group_layout.addRow('Senha antiga:', self.le_senha_antiga)

        self.le_nova_senha = QLineEdit()
        self.le_nova_senha.setPlaceholderText('Nova senha')
        self.le_nova_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.le_nova_senha.setMinimumHeight(40)
        group_layout.addRow('Nova senha:', self.le_nova_senha)

        self.le_confirmar = QLineEdit()
        self.le_confirmar.setPlaceholderText('Confirmar nova senha')
        self.le_confirmar.setEchoMode(QLineEdit.EchoMode.Password)
        self.le_confirmar.setMinimumHeight(40)
        group_layout.addRow('Confirmar nova senha:', self.le_confirmar)

        self.btn_salvar = QPushButton('Salvar')
        self.btn_salvar.setMinimumHeight(40)
        self.btn_salvar.clicked.connect(self.trocar_senha)
        group_layout.addRow(self.btn_salvar)

        group.setLayout(group_layout)
        layout.addWidget(group)
        group.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setAlignment(group, Qt.AlignmentFlag.AlignCenter)

    def trocar_senha(self):
        usuario = self.le_usuario.text().strip()
        senha_antiga = self.le_senha_antiga.text()
        nova_senha = self.le_nova_senha.text()
        confirmar = self.le_confirmar.text()

        if not usuario or not senha_antiga or not nova_senha or not confirmar:
            QMessageBox.warning(self, 'Atenção', 'Preencha todos os campos.')
            return

        if nova_senha != confirmar:
            QMessageBox.warning(self, 'Atenção', 'A nova senha e a confirmação não coincidem.')
            return

        user_data = authenticate_user(usuario, senha_antiga)
        if not user_data:
            QMessageBox.critical(self, 'Erro', 'Usuário ou senha antiga incorretos.')
            return

        senha_hash = _hash_password(nova_senha)
        try:
            update_usuario(usuario, 'senha', senha_hash)
            QMessageBox.information(self, 'Sucesso', 'Senha alterada com sucesso!')
            self.limpar_campos()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Erro ao atualizar senha: {e}')

    def limpar_campos(self):
        self.le_usuario.clear()
        self.le_senha_antiga.clear()
        self.le_nova_senha.clear()
        self.le_confirmar.clear()

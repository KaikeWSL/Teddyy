import os
import logging
import hashlib
import time
from functools import cached_property
from typing import Callable, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (
    QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout, 
    QHBoxLayout, QMessageBox, QCheckBox, QApplication, QFrame,
    QProgressBar
)
from PyQt6.QtGui import QPixmap, QIcon, QKeyEvent, QFont, QPalette
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve

from ..backend.storage_db import authenticate_user, insert_solicitacao
from .tela_cadastro import DialogoSolicitarAcesso

@dataclass(frozen=True)
class LoginConfig:
    """Configurações da janela de login"""
    WINDOW_WIDTH: int = 360
    WINDOW_HEIGHT: int = 520
    MARGIN: int = 30
    SPACING: int = 20
    LOGO_SIZE: int = 110
    INPUT_HEIGHT: int = 45
    BUTTON_HEIGHT: int = 50
    ANIMATION_DURATION: int = 200
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION: int = 60
    PASSWORD_MIN_LENGTH: int = 6
    USERNAME_MIN_LENGTH: int = 3

class LoginSecurity:
    """Gerenciador de segurança do login"""
    
    def __init__(self):
        self._attempts: Dict[str, int] = {}  # username -> tentativas
        self._lockouts: Dict[str, float] = {}  # username -> timestamp
        self._last_attempt: Dict[str, float] = {}  # username -> timestamp
        self._logger = logging.getLogger(__name__)
    
    def is_locked_out(self, username: str) -> bool:
        """Verifica se usuário está bloqueado"""
        if username not in self._lockouts:
            return False
            
        lockout_time = self._lockouts[username]
        if time.time() - lockout_time > LoginConfig.LOCKOUT_DURATION:
            # Remove bloqueio expirado
            del self._lockouts[username]
            del self._attempts[username]
            return False
            
        return True
    
    def get_lockout_time(self, username: str) -> int:
        """Retorna tempo restante de bloqueio em segundos"""
        if not self.is_locked_out(username):
            return 0
            
        elapsed = time.time() - self._lockouts[username]
        return max(0, int(LoginConfig.LOCKOUT_DURATION - elapsed))
    
    def record_attempt(self, username: str, success: bool) -> None:
        """Registra tentativa de login"""
        if success:
            # Reset contadores em caso de sucesso
            self._attempts.pop(username, None)
            self._lockouts.pop(username, None)
            return
            
        # Incrementa contador de tentativas
        self._attempts[username] = self._attempts.get(username, 0) + 1
        self._last_attempt[username] = time.time()
        
        # Verifica se deve bloquear
        if self._attempts[username] >= LoginConfig.MAX_LOGIN_ATTEMPTS:
            self._lockouts[username] = time.time()
            self._logger.warning(
                f"Usuário {username} bloqueado após "
                f"{self._attempts[username]} tentativas falhas"
            )

class StyledLineEdit(QLineEdit):
    """QLineEdit estilizado com validação"""
    
    def __init__(self, placeholder: str = "", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setMinimumHeight(LoginConfig.INPUT_HEIGHT)
        
        # Validação em tempo real
        self.textChanged.connect(self._validate)
        self._error_state = False
    
    def _validate(self):
        """Validação em tempo real"""
        text = self.text().strip()
        if not text:
            self._set_error_state(False)
            return
            
        # Validações específicas por tipo de campo
        if self.placeholderText().lower().startswith("senha"):
            if len(text) < LoginConfig.PASSWORD_MIN_LENGTH:
                self._set_error_state(True)
            else:
                self._set_error_state(False)
        elif self.placeholderText().lower().startswith("login"):
            if len(text) < LoginConfig.USERNAME_MIN_LENGTH:
                self._set_error_state(True)
            else:
                self._set_error_state(False)
    
    def _set_error_state(self, error: bool):
        """Atualiza estado visual de erro"""
        if error != self._error_state:
            self._error_state = error
            if error:
                self.setStyleSheet("border: 1px solid red;")
            else:
                self.setStyleSheet("")

class StyledButton(QPushButton):
    """QPushButton estilizado com efeitos"""
    
    def __init__(self, text: str, primary: bool = True, parent=None):
        super().__init__(text, parent)
        self.primary = primary
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(LoginConfig.BUTTON_HEIGHT)

class TelaLogin(QDialog):
    """Janela de login com segurança aprimorada"""
    
    login_success = pyqtSignal(str, str)  # (nome_usuario, cargo)
    
    def __init__(self, redirecionar_callback: Callable[[str, str], None]) -> None:
        super().__init__()
        self.setObjectName("telaLogin")
        self.redirecionar_callback = redirecionar_callback
        
        # Configurações
        self.WINDOW_WIDTH = LoginConfig.WINDOW_WIDTH
        self.WINDOW_HEIGHT = LoginConfig.WINDOW_HEIGHT
        
        # Estado
        self._is_loading = False
        self._error_timer = QTimer(self)
        self._error_timer.setSingleShot(True)
        self._error_timer.timeout.connect(self._hide_error)
        
        # Segurança
        self._security = LoginSecurity()
        
        # Logger
        self.logger = logging.getLogger(__name__)
        
        # UI
        self._setup_ui()
        self._setup_connections()
        self._setup_shortcuts()
    
    @cached_property
    def logo_path(self) -> str:
        return os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', 'imagens', 'TW-LOGO.png')
        )

    def _setup_ui(self):
        """Configura interface"""
        self.setWindowTitle("Login - Sistema TW")
        self.setFixedSize(self.WINDOW_WIDTH, self.WINDOW_HEIGHT)
        self.setWindowIcon(QIcon('main/imagens/icone.ico'))
        # Centraliza na tela
        screen = QApplication.primaryScreen()
        if screen:
            geometry = screen.geometry()
            self.move(
                (geometry.width() - self.WINDOW_WIDTH) // 2,
                (geometry.height() - self.WINDOW_HEIGHT) // 2
            )
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            LoginConfig.MARGIN,
            LoginConfig.MARGIN,
            LoginConfig.MARGIN,
            LoginConfig.MARGIN
        )
        layout.setSpacing(LoginConfig.SPACING)
        
        
        # Logo
        self.logo_label = QLabel()
        self.logo_label.setObjectName("labelLogo")
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if os.path.exists(self.logo_path):
            pixmap = QPixmap(self.logo_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    LoginConfig.LOGO_SIZE,
                    LoginConfig.LOGO_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.logo_label.setPixmap(scaled_pixmap)
            else:
                self.logo_label.setText("TW")
        else:
            self.logo_label.setText("TW")
        layout.addWidget(self.logo_label)
        layout.addStretch(1)
        
        # Subtítulo
        subtitle = QLabel("Faça login para continuar")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(
            "font-size:12px; font-weight:normal; color:#e0e0e0; background:none;"
        )
       
        
        # Campos
        self.input_usuario = StyledLineEdit("Digite seu login...")
        self.input_senha = StyledLineEdit("Digite sua senha...")
        self.input_senha.setEchoMode(QLineEdit.EchoMode.Password)
        
        layout.addLayout(self._make_labeled_field("Login:", self.input_usuario))
        layout.addLayout(self._make_labeled_field("Senha:", self.input_senha))
        
        # Checkbox
        self.checkbox_manter = QCheckBox("Manter conectado")
        layout.addWidget(self.checkbox_manter)
        
        # Botão Entrar
        self.btn_login = StyledButton("Entrar", primary=True)
        self.btn_login.setObjectName("btnLogin")
        layout.addWidget(self.btn_login)
        
        # Link Solicitar acesso
        self.btn_solicitar = StyledButton("Solicitar Acesso", primary=False)
        self.btn_solicitar.setObjectName("btnSolicitarAcesso")
        layout.addWidget(self.btn_solicitar)
        
        # Barra de progresso
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Mensagem de erro
        self.lbl_erro = QLabel()
        self.lbl_erro.setObjectName("labelErro")
        self.lbl_erro.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_erro.setStyleSheet("color: red")
        self.lbl_erro.hide()
        layout.addWidget(self.lbl_erro)
    
    def _make_labeled_field(self, label_text, field, label_objname=None):
        """Cria um layout vertical com label e campo"""
        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(0, 0, 0, 0)
        
        lab = QLabel(label_text)
        if label_objname:
            lab.setObjectName(label_objname)
            
        layout.addWidget(lab)
        layout.addWidget(field)
        return layout

    def _setup_connections(self):
        self.btn_login.clicked.connect(self._handle_login_click)
        self.btn_solicitar.clicked.connect(self._handle_request_access)
        self.input_usuario.textChanged.connect(self._validate_inputs)
        self.input_senha.textChanged.connect(self._validate_inputs)
        self.login_success.connect(self.redirecionar_callback)

    def _setup_shortcuts(self):
        self.input_usuario.returnPressed.connect(self._handle_login_click)
        self.input_senha.returnPressed.connect(self._handle_login_click)

    def _validate_inputs(self):
        usuario = self.input_usuario.text().strip()
        senha = self.input_senha.text().strip()
        self.btn_login.setEnabled(bool(usuario and senha) and not self._is_loading)
        if self.lbl_erro.isVisible():
            self._hide_error()

    def _handle_login_click(self):
        if self._is_loading:
            return
        try:
            self._set_loading_state(True)
            self._perform_login()
        except Exception as e:
            self.logger.error(f"Login error: {e}")
            self._show_error(f"Erro ao realizar login: {str(e)}")
        finally:
            self._set_loading_state(False)

    def _perform_login(self):
        """Realiza login com validações de segurança"""
        usuario = self.input_usuario.text().strip()
        senha = self.input_senha.text().strip()
        
        # Validações básicas
        if not usuario or not senha:
            self._show_error("Por favor, preencha todos os campos.")
            return
            
        if len(usuario) < LoginConfig.USERNAME_MIN_LENGTH:
            self._show_error(
                f"Usuário deve ter pelo menos {LoginConfig.USERNAME_MIN_LENGTH} caracteres."
            )
            return
            
        if len(senha) < LoginConfig.PASSWORD_MIN_LENGTH:
            self._show_error(
                f"Senha deve ter pelo menos {LoginConfig.PASSWORD_MIN_LENGTH} caracteres."
            )
            return
        
        # Verifica bloqueio
        if self._security.is_locked_out(usuario):
            remaining = self._security.get_lockout_time(usuario)
            self._show_error(
                f"Conta bloqueada. Tente novamente em {remaining} segundos."
            )
            return
        
        try:
            # Tenta autenticação
            resultado = authenticate_user(usuario, senha)
            
            if resultado:
                # Login bem sucedido
                self._security.record_attempt(usuario, True)
                self.logger.info(f"Login realizado: {usuario}")
                self.login_success.emit(resultado["nome"], resultado["cargo"])
                self.close()
            else:
                # Login falhou
                self._security.record_attempt(usuario, False)
                self.logger.warning(f"Falha no login: {usuario}")
                
                # Verifica se foi bloqueado
                if self._security.is_locked_out(usuario):
                    remaining = self._security.get_lockout_time(usuario)
                    self._show_error(
                        f"Muitas tentativas. Conta bloqueada por {remaining} segundos."
                    )
                else:
                    self._show_error("Usuário ou senha inválidos.")
                    
        except Exception as e:
            self.logger.error(f"Erro de autenticação: {e}")
            self._show_error(f"Erro de autenticação: {str(e)}")

    @staticmethod
    def _is_hash(text: str) -> bool:
        """Verifica se texto é um hash SHA-256 válido"""
        return (
            len(text) == 64 and
            all(c in '0123456789abcdefABCDEF' for c in text)
        )

    def _set_loading_state(self, loading: bool):
        """Atualiza estado de carregamento"""
        self._is_loading = loading
        self.btn_login.setEnabled(not loading)
        self.btn_login.setText("Entrando..." if loading else "Entrar")
        self.btn_solicitar.setEnabled(not loading)
        self.input_usuario.setEnabled(not loading)
        self.input_senha.setEnabled(not loading)
        self.progress_bar.setVisible(loading)
        
        if loading:
            self.progress_bar.setRange(0, 0)  # Modo indeterminado
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)

    def _show_error(self, message: str):
        """Mostra mensagem de erro"""
        self.lbl_erro.setText(message)
        self.lbl_erro.show()
        self._error_timer.start(5000)  # 5 segundos
        
        if "Erro ao" in message:
            QMessageBox.critical(self, "Erro", message)

    def _hide_error(self):
        """Esconde mensagem de erro"""
        self.lbl_erro.hide()

    def _handle_request_access(self):
        """Abre diálogo de solicitação de acesso"""
        try:
            nome_detectado = self._get_system_username()
            dialog = DialogoSolicitarAcesso(nome_detectado, parent=self)
            dialog.solicitacao_enviada.connect(self._handle_access_request_submission)
            dialog.exec()
        except Exception as e:
            self.logger.error(f"Erro ao abrir solicitação: {e}")
            self._show_error(f"Erro ao abrir solicitação: {str(e)}")

    def _handle_access_request_submission(
        self,
        usuario: str,
        senha_hash: str,
        nome: str
    ):
        """Processa submissão de solicitação de acesso"""
        try:
            # Validações
            if not all([usuario, senha_hash, nome]):
                raise ValueError("Dados incompletos na solicitação")
                
            if not self._is_hash(senha_hash):
                raise ValueError("Hash de senha inválido")
                
            if len(usuario) < LoginConfig.USERNAME_MIN_LENGTH:
                raise ValueError(
                    f"Usuário deve ter pelo menos {LoginConfig.USERNAME_MIN_LENGTH} caracteres"
                )
            
            # Registra solicitação
            insert_solicitacao(usuario, senha_hash, nome)
            self.logger.info(f"Solicitação enviada para: {usuario}")
            
            QMessageBox.information(
                self,
                "Solicitação Enviada",
                f"Sua solicitação foi registrada com sucesso, {nome}!\n"
                "Aguarde a aprovação do administrador."
            )
            
        except Exception as e:
            self.logger.error(f"Erro na solicitação: {e}")
            self._show_error(f"Falha ao registrar solicitação: {str(e)}")

    def _get_system_username(self) -> str:
        """Obtém nome do usuário do sistema"""
        try:
            return os.getlogin()
        except Exception:
            return os.environ.get('USERNAME', os.environ.get('USER', 'usuario'))

    def keyPressEvent(self, event: QKeyEvent):
        """Trata eventos de teclado"""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not self._is_loading:
                self._handle_login_click()
        elif event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """Trata evento de fechamento"""
        self.logger.info("Janela de login fechada")
        event.accept()
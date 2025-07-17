"""
Access Request Dialog Module

This module provides a dialog for requesting new user access with password validation
and secure hashing functionality.
"""

import hashlib
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

# Configure logging
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DialogConstants:
    """Configuration constants for the access request dialog."""
    
    MIN_PASSWORD_LENGTH: int = 6
    MIN_USERNAME_LENGTH: int = 3
    MIN_WIDTH: int = 400
    MIN_HEIGHT: int = 300
    SPACING: int = 15
    MARGIN: int = 20
    WINDOW_TITLE: str = "Solicitar Primeiro Acesso"
    ICON_FILENAME: str = "icone.png"


class AccessRequestDialog(QDialog):
    """
    Dialog for requesting new user access with secure password handling.
    
    This dialog allows users to create an account by providing a username
    and password, which are validated before being sent to the system.
    
    Signals:
        access_requested: Emitted when access is requested with (username, password_hash, full_name)
    """
    
    access_requested = pyqtSignal(str, str, str)


# Backward compatibility alias - mantenha o nome original para compatibilidade
class DialogoSolicitarAcesso(AccessRequestDialog):
    """
    Alias for backward compatibility with existing code.
    
    This class maintains the original Portuguese class name while using
    the improved implementation.
    """
    
    # Signal alias with original name
    solicitacao_enviada = AccessRequestDialog.access_requested
    
    def __init__(self, nome_completo_ad_detectado: str = "", parent: Optional[QDialog] = None):
        """
        Initialize with original parameter name for compatibility.
        
        Args:
            nome_completo_ad_detectado: Original parameter name (detected full name)
            parent: Parent widget
        """
        super().__init__(detected_full_name=nome_completo_ad_detectado, parent=parent)
    
    def aceitar_solicitacao(self) -> None:
        """Original method name for backward compatibility."""
        self._handle_access_request()
    
    def __init__(self, detected_full_name: str = "", parent: Optional[QDialog] = None):
        """
        Initialize the access request dialog.
        
        Args:
            detected_full_name: The full name detected from AD or other source
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._detected_full_name = detected_full_name.strip()
        self._constants = DialogConstants()
        
        # UI Components - will be initialized in _setup_ui
        self._username_input: Optional[QLineEdit] = None
        self._password_input: Optional[QLineEdit] = None
        self._confirm_password_input: Optional[QLineEdit] = None
        self._button_box: Optional[QDialogButtonBox] = None
        
        self._setup_ui()
        self._connect_signals()
        
        logger.info(f"AccessRequestDialog initialized for user: {detected_full_name}")

    def _setup_ui(self) -> None:
        """Setup the complete user interface."""
        try:
            self._configure_window()
            self._create_layout()
            logger.debug("UI setup completed successfully")
        except Exception as e:
            logger.error(f"Failed to setup UI: {e}")
            self._show_critical_error(f"Erro crítico ao configurar interface: {e}")

    def _configure_window(self) -> None:
        """Configure window properties, title, and icon."""
        self.setWindowTitle(self._constants.WINDOW_TITLE)
        self.setMinimumSize(self._constants.MIN_WIDTH, self._constants.MIN_HEIGHT)
        self.setModal(True)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        
        # Set window icon if available
        icon_path = self._get_icon_path()
        if icon_path and icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
            logger.debug(f"Window icon set: {icon_path}")

    def _get_icon_path(self) -> Optional[Path]:
        """Get the path to the application icon."""
        try:
            current_dir = Path(__file__).parent
            icon_path = current_dir.parent / "imagens" / self._constants.ICON_FILENAME
            return icon_path if icon_path.exists() else None
        except Exception as e:
            logger.warning(f"Could not determine icon path: {e}")
            return None

    def _create_layout(self) -> None:
        """Create and setup the main layout with all components."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(self._constants.SPACING)
        main_layout.setContentsMargins(
            self._constants.MARGIN,
            self._constants.MARGIN,
            self._constants.MARGIN,
            self._constants.MARGIN,
        )
        
        self._add_instruction_label(main_layout)
        self._add_form_fields(main_layout)
        self._add_button_box(main_layout)

    def _add_instruction_label(self, layout: QVBoxLayout) -> None:
        """Add instructional text to the dialog."""
        instruction_text = self._build_instruction_text()
        
        instruction_label = QLabel(instruction_text)
        instruction_label.setWordWrap(True)
       
        
        layout.addWidget(instruction_label)

    def _build_instruction_text(self) -> str:
        """Build the instruction text based on detected name."""
        base_text = (
            "Defina um nome de usuário e senha para solicitar acesso ao sistema.\n"
            "Um administrador aprovará sua solicitação após a análise."
        )
        
        if self._detected_full_name:
            return f"{base_text}\n\nNome detectado: {self._detected_full_name}"
        
        return base_text

    def _add_form_fields(self, layout: QVBoxLayout) -> None:
        """Add all form input fields."""
        self._add_username_field(layout)
        self._add_password_field(layout)
        self._add_confirm_password_field(layout)

    def _add_username_field(self, layout: QVBoxLayout) -> None:
        """Add username input field."""
        username_layout = QHBoxLayout()
        
        username_label = QLabel("Nome de usuário:")
        username_label.setMinimumWidth(100)
        username_layout.addWidget(username_label)
        
        self._username_input = QLineEdit()
        self._username_input.setPlaceholderText("Digite seu nome de usuário...")
        self._username_input.setMaxLength(50)
        username_layout.addWidget(self._username_input)
        
        layout.addLayout(username_layout)

    def _add_password_field(self, layout: QVBoxLayout) -> None:
        """Add password input field."""
        password_layout = QHBoxLayout()
        
        password_label = QLabel("Senha:")
        password_label.setMinimumWidth(100)
        password_layout.addWidget(password_label)
        
        self._password_input = QLineEdit()
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_input.setPlaceholderText(
            f"Mínimo {self._constants.MIN_PASSWORD_LENGTH} caracteres"
        )
        self._password_input.setMaxLength(128)
        password_layout.addWidget(self._password_input)
        
        layout.addLayout(password_layout)

    def _add_confirm_password_field(self, layout: QVBoxLayout) -> None:
        """Add password confirmation field."""
        confirm_layout = QHBoxLayout()
        
        confirm_label = QLabel("Confirmar senha:")
        confirm_label.setMinimumWidth(100)
        confirm_layout.addWidget(confirm_label)
        
        self._confirm_password_input = QLineEdit()
        self._confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_password_input.setPlaceholderText("Digite a senha novamente")
        self._confirm_password_input.setMaxLength(128)
        confirm_layout.addWidget(self._confirm_password_input)
        
        layout.addLayout(confirm_layout)

    def _add_button_box(self, layout: QVBoxLayout) -> None:
        """Add dialog button box."""
        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        
        # Customize button text
        ok_button = self._button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button:
            ok_button.setText("Solicitar Acesso")
        
        cancel_button = self._button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_button:
            cancel_button.setText("Cancelar")
        
        layout.addWidget(self._button_box)

    def _connect_signals(self) -> None:
        """Connect all signal handlers."""
        if self._button_box:
            self._button_box.accepted.connect(self._handle_access_request)
            self._button_box.rejected.connect(self.reject)
        
        # Connect Enter key to submit
        if self._confirm_password_input:
            self._confirm_password_input.returnPressed.connect(self._handle_access_request)

    def _handle_access_request(self) -> None:
        """Handle the access request submission."""
        try:
            if not self._validate_all_inputs():
                return
            
            username = self._get_username()
            password = self._get_password()
            password_hash = self._hash_password(password)
            full_name = self._detected_full_name or username
            
            logger.info(f"Processing access request for username: {username}")
            
            self.access_requested.emit(username, password_hash, full_name)
            self._show_success_message()
            self.accept()
            
        except Exception as e:
            logger.error(f"Error processing access request: {e}")
            self._show_error_message(f"Erro ao processar solicitação: {e}")

    def _validate_all_inputs(self) -> bool:
        """
        Validate all user inputs.
        
        Returns:
            True if all inputs are valid, False otherwise
        """
        username = self._get_username()
        password = self._get_password()
        confirm_password = self._get_confirm_password()
        
        # Check for empty fields
        if not all([username, password, confirm_password]):
            self._show_warning_message(
                "Campos obrigatórios", 
                "Todos os campos devem ser preenchidos."
            )
            return False
        
        # Validate username length
        if len(username) < self._constants.MIN_USERNAME_LENGTH:
            self._show_warning_message(
                "Nome de usuário inválido",
                f"O nome de usuário deve ter pelo menos {self._constants.MIN_USERNAME_LENGTH} caracteres."
            )
            return False
        
        # Validate password length
        if len(password) < self._constants.MIN_PASSWORD_LENGTH:
            self._show_warning_message(
                "Senha inválida",
                f"A senha deve ter pelo menos {self._constants.MIN_PASSWORD_LENGTH} caracteres."
            )
            return False
        
        # Validate password confirmation
        if password != confirm_password:
            self._show_warning_message(
                "Confirmação de senha",
                "As senhas digitadas não coincidem."
            )
            return False
        
        return True

    def _get_username(self) -> str:
        """Get the trimmed username from input."""
        return self._username_input.text().strip() if self._username_input else ""

    def _get_password(self) -> str:
        """Get the password from input."""
        return self._password_input.text() if self._password_input else ""

    def _get_confirm_password(self) -> str:
        """Get the password confirmation from input."""
        return self._confirm_password_input.text() if self._confirm_password_input else ""

    @staticmethod
    def _hash_password(password: str) -> str:
        """
        Hash password using SHA-256.
        
        Args:
            password: Plain text password
            
        Returns:
            Hexadecimal hash of the password
        """
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    def _show_success_message(self) -> None:
        """Show success message to user."""
        QMessageBox.information(
            self,
            "Solicitação Enviada",
            "Sua solicitação de acesso foi registrada com sucesso!\n"
            "Aguarde a aprovação de um administrador."
        )

    def _show_error_message(self, message: str) -> None:
        """Show error message to user."""
        QMessageBox.critical(self, "Erro", message)

    def _show_warning_message(self, title: str, message: str) -> None:
        """Show warning message to user."""
        QMessageBox.warning(self, title, message)

    def _show_critical_error(self, message: str) -> None:
        """Show critical error and close dialog."""
        QMessageBox.critical(
            self,
            "Erro Crítico",
            f"{message}\n\nO diálogo será fechado."
        )
        self.reject()


# Example usage
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Test both classes for compatibility
    dialog = DialogoSolicitarAcesso("João Silva Santos")
    dialog.solicitacao_enviada.connect(
        lambda u, h, n: print(f"Access requested - User: {u}, Hash: {h[:10]}..., Name: {n}")
    )
    
    result = dialog.exec()
    print(f"Dialog result: {result}")
    
    sys.exit(app.exec())
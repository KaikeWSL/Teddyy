from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QProgressBar, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPixmap, QFont, QColor


class SplashScreen(QWidget):
    """
    Tela de carregamento com fundo em gradiente, logo, barra de progresso e animações de fade.
    Após a sequência de passos, emite o sinal finished.
    """
    finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent, flags=Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setFixedSize(500, 320)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Contêiner principal, para aplicar sombra
        container = QWidget(self)
        container.setObjectName("container")
        container.setFixedSize(self.size())
        container.move(0, 0)

        # Efeito de sombra no container
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 0)
        shadow.setColor(QColor(0, 0, 0, 120))
        container.setGraphicsEffect(shadow)

        # Layout interno
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Logo no topo
        logo_label = QLabel()
        logo_pix = QPixmap(self._find_logo_path())
        if not logo_pix.isNull():
            # Ajuste do tamanho do logo proporcionalmente
            logo_pix = logo_pix.scaledToWidth(120, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(logo_pix)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo_label)

        # Título principal
        title = QLabel("Sistema TW")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #F5F5F5;")
        layout.addWidget(title)

        # Versão / subtítulo
        version = QLabel("v1.0.0")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setFont(QFont("Segoe UI", 10))
        version.setStyleSheet("color: #DDDDDD;")
        layout.addWidget(version)

        # Mensagem de status
        self.status_label = QLabel("Inicializando...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(QFont("Segoe UI", 11))
        self.status_label.setStyleSheet("color: #EEEEEE;")
        layout.addWidget(self.status_label)

        # Barra de progresso customizada
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(18)
        self.progress.setStyleSheet(
            """
            QProgressBar {
                border: 1px solid #444444;
                border-radius: 9px;
                background-color: #2E2E2E;
            }
            QProgressBar::chunk {
                border-radius: 9px;
                background-color: #00C853;
            }
            """
        )
        layout.addWidget(self.progress)

        # Passos de carregamento: (delay_ms, valor_pct, mensagem)
        self._steps = [
            (400, 15,  "Conectando ao banco de dados..."),
            (400, 35,  "Conectando ao banco de dados..."),
            (700, 40,  "Autenticando usuário..."),
            (700, 60,  "Autenticando usuário..."),
            (1300, 77, "Carregando configurações..."),
            (1300, 95, "Carregando configurações..."),
            (1500, 100, "Entrando...")
        ]
        self._current = 0

        # Preparar animação de fade-in
        self._prepare_fade_animation()

    def _find_logo_path(self) -> str:
        """
        Retorna o caminho para o arquivo de logo. Ajuste conforme necessário.
        """
        base = Path(__file__).parent
        possível = base / "logo.png"
        if possível.exists():
            return str(possível)
        return ""

    def _prepare_fade_animation(self):
        """Configura animação de fade-in ao exibir a splash."""
        self.setWindowOpacity(0.0)
        self.fade_in = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in.setDuration(500)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.fade_out = QPropertyAnimation(self, b"windowOpacity")
        self.fade_out.setDuration(300)
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)
        self.fade_out.setEasingCurve(QEasingCurve.Type.InOutQuad)

        # Quando terminar o fade-out, emite finished
        self.fade_out.finished.connect(self._emit_finished)

    def start(self):
        """Exibe a splash (com fade-in) e inicia a sequência de passos."""
        self.show()
        self.fade_in.start()
        # Aguarda o fade-in terminar antes de iniciar steps
        QTimer.singleShot(self.fade_in.duration(), lambda: self._schedule_next_step())

    def _schedule_next_step(self):
        """Dispara o próximo passo de acordo com o delay configurado."""
        delay, _, _ = self._steps[0]
        QTimer.singleShot(delay, self._next)

    def _next(self):
        _, pct, msg = self._steps[self._current]
        self.progress.setValue(pct)
        self.status_label.setText(msg)
        self._current += 1

        if self._current < len(self._steps):
            delay, _, _ = self._steps[self._current]
            QTimer.singleShot(delay, self._next)
        else:
            # Todos os passos concluídos, aguardar um momento e iniciar fade-out
            QTimer.singleShot(500, self._start_fade_out)

    def _start_fade_out(self):
        """Inicia animação de fade-out antes de fechar."""
        self.fade_out.start()

    def _emit_finished(self):
        """Encerra a splash e emite o sinal finished."""
        self.close()
        self.finished.emit()

    def closeEvent(self, event):
        """
        Impede fechamento manual; só permite fechar após todos os passos e fade-out.
        """
        if self._current < len(self._steps) or self.windowOpacity() > 0.0:
            event.ignore()
        else:
            super().closeEvent(event)

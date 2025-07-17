import os
import datetime
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QStackedWidget, QMessageBox
)
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from ..backend.storage_db import get_table_normalized
from ..backend.format_utils import parse_currency

class GraphMensalWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent
        # Carrega dataframe do banco
        records = get_table_normalized('os_cadastros')
        self.df = pd.DataFrame(records)
        self.df.drop(columns=['id'], inplace=True, errors='ignore')

        self.current_year = datetime.datetime.now().year
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Ano:"))
        self.year_combo = QComboBox()
        icon_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "imagens", "seta.png"
        ))
        icon_url = icon_path.replace("\\", "/")
        self.year_combo.setStyleSheet(f"""
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
        self.year_combo.addItems([str(self.current_year - i) for i in range(5)])
        self.year_combo.setCurrentText(str(self.current_year))
        btn = QPushButton("Gerar Mensal")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self.plot)
        self.year_combo.currentIndexChanged.connect(self.plot)
        ctrl.addWidget(self.year_combo)

        self.figure = Figure(facecolor='#2c3e50')
        self.canvas = FigureCanvas(self.figure)

        layout = QVBoxLayout(self)
        layout.addLayout(ctrl)
        layout.addWidget(self.canvas)

        self.plot()

    def plot(self):
        try:
            year = int(self.year_combo.currentText())
            df = self.df.copy()
            if df.empty:
                raise ValueError("DataFrame vazio")
            df['saida'] = pd.to_datetime(df['saida_equip'], dayfirst=True, errors='coerce')
            df['valor_num'] = df['valor'].apply(lambda x: parse_currency(x) if isinstance(x, str) else float(x) if pd.notna(x) else 0)
            df = df.dropna(subset=['saida', 'valor_num'])
            df_year = df[df['saida'].dt.year == year]
            mensal = df_year.groupby(df_year['saida'].dt.month)['valor_num'].sum()

            months = list(range(1,13))
            values = [mensal.get(m, 0.0) for m in months]
            max_val = max(values) if values else 0

            self.figure.clear()
            ax = self.figure.add_subplot(111, facecolor='#2c3e50')
            bars = ax.bar(months, values, color="#60a3fc")

            # Destaque melhor e pior mês
            if values:
                idx_max = values.index(max_val)
                idx_min = values.index(min([v for v in values if v > 0], default=0)) if any(v > 0 for v in values) else None
                for i, bar in enumerate(bars):
                    if i == idx_max and values[i] > 0:
                        bar.set_color("#4be169")  # Verde para o melhor mês
                    elif idx_min is not None and i == idx_min and values[i] > 0:
                        bar.set_color("#eb6a64")  # Vermelho para o pior mês
                    # O restante permanece azul padrão

            ax.set_ylim(0, max_val * 1.4 if max_val > 0 else 1)
            top_offset = max_val * 0.01

            # Exibe valores nas barras
            for rect in bars:
                val = rect.get_height()
                if val <= 0:
                    continue
                s = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                label = f"R$ {s}"
                ax.text(
                    rect.get_x() + rect.get_width()/2,
                    val + top_offset,
                    label,
                    ha='center', va='bottom',
                    color='white', fontweight='bold', fontsize=10, rotation=90
                )
            ax.set_title(f"Faturamento Mensal {year} (Total: R$ {sum(values):,.2f})".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        color='white', fontsize=15, fontweight='bold')
            meses_abrev = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
            ax.set_xticks(months)
            ax.set_xticklabels(meses_abrev, color='white', fontsize=12)
            ax.tick_params(colors='white')
            ax.grid(axis='y', color='#444', linestyle=':', alpha=0.5)
            for spine in ax.spines.values():
                spine.set_color('white')
            self.figure.tight_layout()
            self.canvas.draw()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao plotar gráfico mensal: {e}")


class GraphComparativoWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Carrega dataframe do banco
        records = get_table_normalized('os_cadastros')
        self.df = pd.DataFrame(records)
        self.df.drop(columns=['id'], inplace=True, errors='ignore')

        now = datetime.datetime.now().year
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Ano 1:"))
        self.combo_y1 = QComboBox()
        icon_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "imagens", "seta.png"
        ))
        icon_url = icon_path.replace("\\", "/")
        self.combo_y1.setStyleSheet(f"""
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
        ctrl.addWidget(self.combo_y1)
        ctrl.addWidget(QLabel("Ano 2:"))
        self.combo_y2 = QComboBox()
        self.combo_y2.setStyleSheet(f"""
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
        ctrl.addWidget(self.combo_y2)
        years = [str(now - i) for i in range(5)]
        self.combo_y1.addItems(years)
        self.combo_y2.addItems(years)
        self.combo_y1.setCurrentText(str(now))
        self.combo_y2.setCurrentText(str(now - 1))
        btn = QPushButton("Gerar Comparativo")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self.plot)
        self.combo_y1.currentIndexChanged.connect(self.plot)
        self.combo_y2.currentIndexChanged.connect(self.plot)

        self.figure = Figure(facecolor='#2c3e50')
        self.canvas = FigureCanvas(self.figure)

        layout = QVBoxLayout(self)
        layout.addLayout(ctrl)
        layout.addWidget(self.canvas)

        self.plot()

    def plot(self):
        try:
            y1 = int(self.combo_y1.currentText())
            y2 = int(self.combo_y2.currentText())
            df = self.df.copy()
            if df.empty:
                raise ValueError("DataFrame vazio")
            df['saida'] = pd.to_datetime(df['saida_equip'], dayfirst=True, errors='coerce')
            df['valor_num'] = df['valor'].apply(lambda x: parse_currency(x) if isinstance(x, str) else float(x) if pd.notna(x) else 0)
            df = df.dropna(subset=['saida', 'valor_num'])
            df1 = df[df['saida'].dt.year == y1]
            df2 = df[df['saida'].dt.year == y2]
            m1 = df1.groupby(df1['saida'].dt.month)['valor_num'].sum()
            m2 = df2.groupby(df2['saida'].dt.month)['valor_num'].sum()
            months = list(range(1, 13))
            vals1 = [m1.get(m, 0.0) for m in months]
            vals2 = [m2.get(m, 0.0) for m in months]
            total1, total2 = sum(vals1), sum(vals2)

            # Calcula variação percentual mês a mês
            var_perc = []
            for v2, v1 in zip(vals2, vals1):
                if v2 == 0 and v1 == 0:
                    var_perc.append(0)
                elif v2 == 0:
                    var_perc.append(-100)
                else:
                    var_perc.append(((v1 - v2) / v2) * 100)

            self.figure.clear()
            ax = self.figure.add_subplot(111, facecolor='#2c3e50')
            bar1 = ax.bar([m-0.2 for m in months], vals1, width=0.4, label=str(y1), color="#60a3fc")
            bar2 = ax.bar([m+0.2 for m in months], vals2, width=0.4, label=str(y2), color="#3fd1c7")

            # Remover destaque de melhor e pior mês (todas as barras ficam com a cor padrão)
            # if vals1:
            #     vals1_valid = [v for v in vals1 if v is not None and v > 0]
            #     if vals1_valid:
            #         max1 = max(vals1_valid)
            #         min1 = min(vals1_valid)
            #         for idx, val in enumerate(vals1):
            #             if val == max1 and val > 0:
            #                 bar1[idx].set_color("#4be169")  # Verde melhor mês ano 1
            #             elif val == min1 and val > 0:
            #                 bar1[idx].set_color("#eb6a64")  # Vermelho pior mês ano 1
            # if vals2:
            #     vals2_valid = [v for v in vals2 if v is not None and v > 0]
            #     if vals2_valid:
            #         max2 = max(vals2_valid)
            #         min2 = min(vals2_valid)
            #         for idx, val in enumerate(vals2):
            #             if val == max2 and val > 0:
            #                 bar2[idx].set_color("#4be169")  # Verde melhor mês ano 2
            #             elif val == min2 and val > 0:
            #                 bar2[idx].set_color("#eb6a64")  # Vermelho pior mês ano 2

            max_val = max([v for v in (vals1 + vals2) if v is not None], default=0) if vals1 or vals2 else 0
            
            # MELHORIA: Aumentar o limite superior para dar mais espaço aos textos
            ax.set_ylim(0, max_val * 2.0 if max_val > 0 else 1)
            
            # MELHORIA: Calcular offsets mais precisos
            top_offset = max_val * 0.02
            perc_offset = max_val * 0.05   # Espaço para porcentagem
            valor_offset = max_val * 0.15  # Espaço adicional para valor (acima da porcentagem)

            # MELHORIA: Exibe valor e porcentagem com melhor posicionamento
            for i, (rect1, rect2, perc) in enumerate(zip(bar1, bar2, var_perc)):
                val1, val2 = rect1.get_height(), rect2.get_height()
                x1 = rect1.get_x() + rect1.get_width() / 2
                x2 = rect2.get_x() + rect2.get_width() / 2
                x_centro = months[i]  # posição central do mês
                y_base = max(val1, val2)
                # Porcentagem (centralizada entre as barras)
                if val1 > 0 or val2 > 0:
                    cor = "#4be169" if perc > 0 else "#eb6a64" if perc < 0 else "#bfbfbf"
                    signal = "↑" if perc > 0 else "↓" if perc < 0 else ""
                    y_perc = y_base + perc_offset
                    ax.text(x_centro, y_perc, f"{signal}{abs(perc):.1f}%", 
                        ha='center', va='bottom', color=cor, fontsize=10, fontweight='bold')
                # Valor de cada barra, acima de cada barra, rotacionado 90 graus
                if val1 > 0:
                    s1 = f"{val1:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    y_valor1 = val1 + valor_offset
                    ax.text(x1, y_valor1, f"R$ {s1}",
                        ha='center', va='bottom', color='white',
                        rotation=90, fontsize=9, fontweight='bold')
                if val2 > 0:
                    s2 = f"{val2:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    y_valor2 = val2 + valor_offset
                    ax.text(x2, y_valor2, f"R$ {s2}",
                        ha='center', va='bottom', color='white',
                        rotation=90, fontsize=9, fontweight='bold')

            # MELHORIA: Totais e variação posicionados mais acima
            diff_abs = total1 - total2
            diff_perc = ((total1 - total2) / total2 * 100) if total2 else 0
            cor_diff = "#4be169" if diff_perc > 0 else "#eb6a64" if diff_perc < 0 else "#bfbfbf"
            sinal_diff = "↑" if diff_perc > 0 else "↓" if diff_perc < 0 else ""
            
            # MELHORIA: Título e totais posicionados mais acima e melhor centralizados
            # Título e totais FORA da área do gráfico (acima da linha)
            # Título dentro da área do gráfico
            ax.set_title(f"Comparativo {y1} vs {y2}", color='white', fontsize=16, fontweight='bold', pad=20)
            # Remover o suptitle
            self.figure.suptitle("")
            # Totais e variação logo abaixo do título, ainda fora do gráfico
            totais_text = (
                f"{y1}: R$ {total1:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') +
                f"\n{y2}: R$ {total2:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            )
            var_text = f"{sinal_diff}{abs(diff_perc):.1f}% (Dif: R$ {diff_abs:,.2f})".replace(',', 'X').replace('.', ',').replace('X', '.')
            self.figure.text(0.99, 0.99, totais_text, ha='right', va='top', color='white', fontsize=12, fontweight='bold', transform=self.figure.transFigure)
            self.figure.text(0.99, 0.90, var_text, ha='right', va='top', color=cor_diff, fontsize=12, fontweight='bold', transform=self.figure.transFigure)

            # Remove os textos do topo do ax (dentro do gráfico)
            # (remover as linhas de ax.text para título/totais/variação)

            # Nomes dos meses abreviados em português
            meses_abrev = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
            ax.set_xticks(months)
            ax.set_xticklabels(meses_abrev, color='white', fontsize=12)
            ax.legend(facecolor='#1b4d7a', edgecolor='white', labelcolor='white', fontsize=11)
            ax.tick_params(colors='white')
            ax.grid(axis='y', color='#444', linestyle=':', alpha=0.5)
            for spine in ax.spines.values():
                spine.set_color('white')
            
            # MELHORIA: Ajustar margens para acomodar o texto superior
            self.figure.subplots_adjust(top=0.85, bottom=0.1, left=0.1, right=0.95)
            self.canvas.draw()
            
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao plotar gráfico comparativo: {e}")


class TelaGraficos(QWidget):
    """Tela principal: alterna entre gráficos mensal e comparativo."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gráficos")
        self.setObjectName("telaGraficos")
        layout = QVBoxLayout(self)

        btn_layout = QHBoxLayout()
        btn_m = QPushButton("Mensal")
        btn_m.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_c = QPushButton("Comparativo")
        btn_c.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_layout.addWidget(btn_m)
        btn_layout.addWidget(btn_c)
        layout.addLayout(btn_layout)

        # Data vem do banco, não excel
        self.stack = QStackedWidget()
        self.mensal = GraphMensalWidget(self)
        self.comp = GraphComparativoWidget(self)
        self.stack.addWidget(self.mensal)
        self.stack.addWidget(self.comp)
        layout.addWidget(self.stack)

        btn_m.clicked.connect(lambda: self.stack.setCurrentWidget(self.mensal))
        btn_c.clicked.connect(lambda: self.stack.setCurrentWidget(self.comp))
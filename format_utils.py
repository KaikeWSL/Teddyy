# main/backend/format_utils.py

from PyQt6.QtGui import QValidator


def format_brl(value: str) -> str:
    """
    Formata uma string numérica em Real brasileiro:
    - Recebe algo como "1234.56" ou "1234,56" ou "R$ 1.234,56"
    - Retorna "R$ 1.234,56"
    """
    try:
        # remove "R$" e espaços
        v = value.replace("R$", "").strip()
        # ponto como separador decimal
        number = float(v.replace(",", "."))
        formatted = f"R$ {number:,.2f}"
        # troca vírgula e ponto para o padrão BR
        formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
        return formatted
    except Exception:
        return value


def validate_currency(P: str) -> bool:
    """
    Retorna True se a string P for um formato de moeda BR válido (sem formatação final).
    Usado internamente pelo CurrencyValidator.
    """
    if P == "":
        return True
    # remove possível "R$"
    t = P.replace("R$", "").strip()
    # trata separador de milhares
    if "," in t:
        partes = t.split(",")
        partes[0] = partes[0].replace(".", "")
        t = partes[0] + "," + partes[1]
    else:
        t = t.replace(".", "")
    try:
        float(t.replace(",", "."))
        return True
    except ValueError:
        return False


class CurrencyValidator(QValidator):
    """
    QValidator para campos de moeda BR.
    Usa a função validate_currency acima.
    """
    def validate(self, input_str: str, pos: int):
        if validate_currency(input_str):
            return QValidator.State.Acceptable, input_str, pos
        return QValidator.State.Invalid, input_str, pos


def parse_currency(value: str) -> float | None:
    """
    Converte uma string formatada em Real (e.g. "R$ 1.234,56") para float.
    Retorna None se não conseguir converter.
    """
    try:
        v = value.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
        return float(v)
    except Exception:
        return None

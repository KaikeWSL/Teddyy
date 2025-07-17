# migrate_data.py

import os
import json
import pandas as pd
from db_connection import get_conn, put_conn, close_pool

def migrar_usuarios():
    conn = get_conn()
    cur = conn.cursor()
    path = os.path.join('data', 'usuarios.json')
    with open(path, 'r', encoding='utf-8') as f:
        usuarios = json.load(f)
    for usuario, dados in usuarios.items():
        cur.execute(
            """
            INSERT INTO usuarios(usuario, senha, nome, cargo)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (usuario) DO UPDATE
              SET senha = EXCLUDED.senha,
                  nome  = EXCLUDED.nome,
                  cargo = EXCLUDED.cargo;
            """,
            (usuario, dados['senha'], dados['nome'], dados.get('cargo', ''))
        )
    conn.commit()
    cur.close()
    put_conn(conn)

def migrar_solicitacoes():
    conn = get_conn()
    cur = conn.cursor()
    path = os.path.join('data', 'solicitacoes.json')
    with open(path, 'r', encoding='utf-8') as f:
        lista = json.load(f)
    for item in lista:
        cur.execute(
            """
            INSERT INTO solicitacoes(usuario, senha_hash, nome)
            VALUES (%s, %s, %s)
            ON CONFLICT (usuario) DO UPDATE
              SET senha_hash = EXCLUDED.senha_hash,
                  nome       = EXCLUDED.nome;
            """,
            (item['usuario'], item['senha_hash'], item['nome'])
        )
    conn.commit()
    cur.close()
    put_conn(conn)

def migrar_clientes():
    conn = get_conn()
    cur = conn.cursor()
    # ajusta caminho para a pasta data na raiz do projeto
    import os
    proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    path = os.path.join(proj_root, 'data', 'clientes.json')
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # normaliza para lista de dicts mesmo se for dict de nome→info
    if isinstance(data, dict):
        clientes_list = [{'nome': nome, **info} for nome, info in data.items()]
    else:
        clientes_list = data

    for cli in clientes_list:
        nome        = cli['nome']
        cpf_cnpj    = cli.get('cpf_cnpj','')
        endereco    = cli.get('endereco','')
        bairro      = cli.get('bairro','')
        numero      = cli.get('numero','')
        email       = cli.get('email','')
        contato     = cli.get('nome_contato','')
        tel_contato = cli.get('tel_contato','')

        cur.execute(
            """
            INSERT INTO clientes(
                nome, cpf_cnpj, endereco, bairro, numero,
                email, nome_contato, tel_contato
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (nome) DO UPDATE SET
                cpf_cnpj     = EXCLUDED.cpf_cnpj,
                endereco     = EXCLUDED.endereco,
                bairro       = EXCLUDED.bairro,
                numero       = EXCLUDED.numero,
                email        = EXCLUDED.email,
                nome_contato = EXCLUDED.nome_contato,
                tel_contato  = EXCLUDED.tel_contato;
            """,
            (nome, cpf_cnpj, endereco, bairro, numero, email, contato, tel_contato)
        )

    conn.commit()
    cur.close()
    put_conn(conn)


def migrar_equipamentos():
    conn = get_conn()
    cur = conn.cursor()
    path = os.path.join('data', 'modelos.json')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            equipamentos = json.load(f).items()
    else:
        equipamentos = []
    for modelo, info in equipamentos:
        tipo, marca = info
        cur.execute(
            """
            INSERT INTO equipamentos(equipamento, tipo, marca)
            VALUES (%s, %s, %s)
            ON CONFLICT (equipamento) DO UPDATE
              SET tipo  = EXCLUDED.tipo,
                  marca = EXCLUDED.marca;
            """,
            (modelo, tipo, marca)
        )
    conn.commit()
    cur.close()
    put_conn(conn)

def migrar_os():
    conn = get_conn()
    cur = conn.cursor()
    path = os.path.join('data', 'Cadastros.xlsx')
    df = pd.read_excel(path, dtype=str)

    for _, row in df.iterrows():
        entrada = pd.to_datetime(row['Entrada equip.'], dayfirst=True, errors='coerce')
        saida   = pd.to_datetime(row['Saída equip.'],   dayfirst=True, errors='coerce')
        valor   = row['Valor'].replace('R$', '').replace('.', '').replace(',', '.') if row['Valor'] else None

        cur.execute(
            """
            INSERT INTO os_cadastros(
              cliente, modelo, os, entrada_equip, valor, saida_equip,
              serie, tecnico, pagamento, vezes, data_pag1, data_pag2, data_pag3,
              avaliacao_tecnica, causa_provavel
            ) VALUES (
              %s, %s, %s, %s, %s, %s,
              %s, %s, 0, 0, NULL, NULL, NULL, '', ''
            )
            ON CONFLICT (os) DO UPDATE
              SET cliente = EXCLUDED.cliente,
                  modelo  = EXCLUDED.modelo,
                  entrada_equip = EXCLUDED.entrada_equip,
                  valor   = EXCLUDED.valor,
                  saida_equip  = EXCLUDED.saida_equip,
                  serie   = EXCLUDED.serie,
                  tecnico = EXCLUDED.tecnico;
            """,
            (
                row['Cliente'], row['Modelo'], row['OS'],
                entrada.date() if not pd.isna(entrada) else None,
                float(valor) if valor else None,
                saida.date() if not pd.isna(saida) else None,
                row['N° serie'], row['Técnico']
            )
        )
    conn.commit()
    cur.close()
    put_conn(conn)

def main():

    migrar_os()
    close_pool()
    print("✅ Migração concluída com sucesso.")

if __name__ == '__main__':
    main()

"""
Testes de carga_postgres.py que NÃO usam um PostgreSQL real.

O banco é simulado por uma conexão "falsa" (ConexaoFalsa), que responde às
consultas de conferência, guarda os INSERTs em memória e registra se houve
COMMIT ou ROLLBACK. Assim é possível testar a transação e as falhas sem
gravar nada.

Execute a partir da pasta Entrega_final:
    python -m unittest discover -s tests -v
"""

import contextlib
import copy
import importlib.util
import io
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

PASTA_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PASTA_PROJETO))
os.chdir(PASTA_PROJETO)  # os caminhos dos CSVs são relativos à pasta do projeto

import carga_postgres as cp  # noqa: E402

PSYCOPG_INSTALADO = importlib.util.find_spec("psycopg") is not None
COMANDOS_PROIBIDOS = re.compile(r"\b(TRUNCATE|DELETE|DROP|UPDATE|ALTER|CREATE)\b", re.IGNORECASE)


def texto_sql(consulta):
    """Converte a consulta (texto ou psycopg.sql) em texto para inspeção."""
    return consulta.as_string(None) if hasattr(consulta, "as_string") else str(consulta)


class CursorFalso:
    """Imita um cursor do psycopg, respondendo às consultas de conferência."""

    def __init__(self, conexao):
        self.conexao = conexao
        self.resultado = []

    def execute(self, consulta, parametros=None):
        sql = texto_sql(consulta)
        self.conexao.comandos.append((sql, parametros))
        cenario = self.conexao.cenario
        if "current_database()" in sql:
            self.resultado = [(cenario["banco"],)]
        elif "pg_namespace WHERE nspname" in sql:
            self.resultado = [(cenario["schema_existe"],)]
        elif "information_schema.columns" in sql:
            self.resultado = cenario["colunas"].get(parametros[1], [])
        elif "pg_constraint" in sql:
            self.resultado = list(cenario["restricoes"].get(parametros[1], {}).items())
        elif sql.startswith("SELECT EXISTS (SELECT 1 FROM"):
            tabela = sql.split(".")[-1].strip('")')
            self.resultado = [(tabela in cenario["tabelas_com_dados"],)]
        elif "GROUP BY situacao_ideb" in sql or "ANY(%s)" in sql:
            self.resultado = []  # consultas que devolvem várias linhas
        else:
            self.resultado = [(0,)]

    def executemany(self, consulta, registros):
        sql = texto_sql(consulta)
        tabela = sql.split('"educacao"."')[1].split('"')[0]
        self.conexao.comandos.append((sql, None))
        if tabela == self.conexao.cenario.get("falhar_no_insert"):
            raise RuntimeError(f"falha simulada ao inserir em {tabela}")
        self.conexao.inseridos[tabela] = len(registros)
        self.conexao.parametros_insert.extend(registros[:3])

    def fetchone(self):
        return self.resultado[0]

    def fetchall(self):
        return self.resultado

    def close(self):
        pass


class ConexaoFalsa:
    """Imita uma conexão do psycopg e registra COMMIT/ROLLBACK."""

    def __init__(self, **alteracoes):
        self.cenario = cenario_correto()
        self.cenario.update(alteracoes)
        self.comandos, self.inseridos, self.parametros_insert = [], {}, []
        self.commits = self.rollbacks = 0

    def cursor(self):
        return CursorFalso(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def colunas_como_no_catalogo(tabela):
    """Gera as linhas que information_schema.columns devolveria pelo DDL."""
    precisao_inteiros = {cp.SMALLINT: 16, cp.INTEGER: 32}
    return [
        (c.nome, c.tipo, c.tamanho, c.precisao or precisao_inteiros.get(c.tipo),
         0 if c.tipo in precisao_inteiros else c.escala,
         "YES" if c.aceita_nulo else "NO")
        for c in cp.CONTRATO[tabela]
    ]


def cenario_correto():
    return {
        "banco": cp.BANCO,
        "schema_existe": True,
        "colunas": {t: colunas_como_no_catalogo(t) for t in cp.ORDEM_CARGA},
        "restricoes": copy.deepcopy(cp.RESTRICOES_ESPERADAS),
        "tabelas_com_dados": set(),
    }


def silencioso(funcao, *args, **kwargs):
    """Executa sem poluir a saída dos testes."""
    with contextlib.redirect_stdout(io.StringIO()):
        return funcao(*args, **kwargs)


class TestePreparacaoLocal(unittest.TestCase):
    """Dry-run e preparação dos dados (não precisam do psycopg)."""

    @classmethod
    def setUpClass(cls):
        cls.tabelas, cls.plano, cls.relatorio = silencioso(cp.preparar_e_validar)
        cls.esperado = cp.calcular_esperado(cls.tabelas)

    def test_contagens_e_validacoes(self):
        self.assertEqual(self.relatorio.falhas(), [])
        self.assertEqual({i["tabela"]: len(i["registros"]) for i in self.plano},
                         cp.CONTAGENS_ESPERADAS)
        self.assertEqual(self.esperado["sem_ideb"], 377)
        self.assertEqual(self.esperado["sem_registro_matricula"], 718)

    def test_ordem_de_carga_respeita_fks(self):
        self.assertEqual([i["tabela"] for i in self.plano], cp.ORDEM_CARGA)

    def test_registros_so_tem_tipos_python_simples(self):
        for item in self.plano:
            for registro in item["registros"]:
                for valor in registro:
                    self.assertIsInstance(valor, cp.TIPOS_ACEITOS_PELO_DRIVER)

    def test_nulos_viram_none_e_nunca_zero(self):
        indicador = next(i for i in self.plano if i["tabela"] == "indicador_educacional")
        posicao_ideb = indicador["colunas"].index("vl_ideb")
        posicao_situacao = indicador["colunas"].index("situacao_ideb")
        for registro in indicador["registros"]:
            if registro[posicao_situacao] != "Divulgado":
                self.assertIsNone(registro[posicao_ideb])

    def test_escolas_de_interesse_esperadas(self):
        linhas = {(r[0], r[1]): r for r in self.esperado["escolas_interesse"]}
        self.assertEqual(str(linhas[("35010281", "AI")][-1]), "6.4")
        self.assertEqual(str(linhas[("35044386", "AF")][-1]), "3.9")
        self.assertIsNone(linhas[("35044386", "EM")][-1])
        self.assertEqual(linhas[("35044386", "EM")][2], 393)

    def test_dry_run_nao_abre_conexao_nem_importa_driver(self):
        """Executa o dry-run com a rede bloqueada: qualquer conexão daria erro."""
        codigo = (
            "import socket, sys, runpy\n"
            "def bloqueado(*a, **k): raise RuntimeError('tentativa de conexão de rede')\n"
            "socket.socket.connect = bloqueado; socket.socket.connect_ex = bloqueado\n"
            "socket.create_connection = bloqueado\n"
            "sys.argv = ['carga_postgres.py', '--dry-run']\n"
            "try:\n"
            "    runpy.run_path('carga_postgres.py', run_name='__main__')\n"
            "except SystemExit as fim:\n"
            "    print('psycopg importado:', 'psycopg' in sys.modules); sys.exit(fim.code)\n"
        )
        resultado = subprocess.run([sys.executable, "-c", codigo], capture_output=True,
                                   text=True, encoding="utf-8", cwd=PASTA_PROJETO,
                                   env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        self.assertIn("psycopg importado: False", resultado.stdout)
        self.assertIn("0 falhas", resultado.stdout)

    def test_sem_modo_nao_executa_nada(self):
        self.assertEqual(silencioso(cp.main, []), 2)

    def test_codigo_nao_tem_comandos_de_exclusao(self):
        fonte = (PASTA_PROJETO / "carga_postgres.py").read_text(encoding="utf-8")
        literais = re.findall(r'"""(.*?)"""|"([^"\n]*)"', fonte, flags=re.DOTALL)
        sql_no_codigo = " ".join(a or b for a, b in literais if "SELECT" in (a or b)
                                 or "INSERT" in (a or b) or "LOCK" in (a or b))
        self.assertIsNone(COMANDOS_PROIBIDOS.search(sql_no_codigo))


@unittest.skipUnless(PSYCOPG_INSTALADO, "psycopg não instalado")
class TesteTransacaoSimulada(unittest.TestCase):
    """Carga com banco simulado: COMMIT, ROLLBACK e recusas."""

    @classmethod
    def setUpClass(cls):
        cls.tabelas, cls.plano, _ = silencioso(cp.preparar_e_validar)
        cls.esperado = cp.calcular_esperado(cls.tabelas)

    def carregar(self, conexao, medir=None):
        medir = medir or (lambda cursor: copy.deepcopy(self.esperado))
        return silencioso(cp.executar_carga, conexao, self.plano, self.esperado, medir)

    def test_carga_correta_faz_commit(self):
        conexao = ConexaoFalsa()
        self.carregar(conexao)
        self.assertEqual((conexao.commits, conexao.rollbacks), (1, 0))
        self.assertEqual(list(conexao.inseridos), cp.ORDEM_CARGA)
        self.assertEqual(conexao.inseridos, cp.CONTAGENS_ESPERADAS)

    def test_sql_parametrizado_e_sem_comandos_proibidos(self):
        conexao = ConexaoFalsa()
        self.carregar(conexao)
        inserts = [sql for sql, _ in conexao.comandos if sql.startswith("INSERT")]
        self.assertEqual(len(inserts), 4)
        for sql, _ in conexao.comandos:
            self.assertIsNone(COMANDOS_PROIBIDOS.search(sql), sql)
            self.assertNotIn("35010281", sql)  # dados nunca entram no texto SQL
        for sql in inserts:
            self.assertIn("%s", sql)

    def test_tabela_com_dados_e_recusada_sem_insert(self):
        conexao = ConexaoFalsa(tabelas_com_dados={"escola"})
        with self.assertRaisesRegex(cp.ErroCarga, "já possuem registros"):
            self.carregar(conexao)
        self.assertEqual((conexao.commits, conexao.rollbacks), (0, 1))
        self.assertEqual(conexao.inseridos, {})

    def test_banco_errado_e_recusado(self):
        conexao = ConexaoFalsa(banco="postgres")
        with self.assertRaisesRegex(cp.ErroCarga, "Banco incorreto"):
            self.carregar(conexao)
        self.assertEqual((conexao.commits, conexao.rollbacks, conexao.inseridos), (0, 1, {}))

    def test_schema_inexistente_e_recusado(self):
        conexao = ConexaoFalsa(schema_existe=False)
        with self.assertRaisesRegex(cp.ErroCarga, "schema"):
            self.carregar(conexao)
        self.assertEqual(conexao.inseridos, {})

    def test_tabela_inexistente_e_recusada(self):
        cenario = cenario_correto()
        del cenario["colunas"]["indicador_educacional"]
        conexao = ConexaoFalsa(colunas=cenario["colunas"])
        with self.assertRaisesRegex(cp.ErroCarga, "não existe"):
            self.carregar(conexao)
        self.assertEqual(conexao.inseridos, {})

    def test_estrutura_diferente_e_recusada(self):
        cenario = cenario_correto()
        colunas = cenario["colunas"]["indicador_educacional"]
        colunas[-1] = ("vl_ideb", "numeric", None, 4, 2, "YES")  # NUMERIC(4,2) no lugar de (3,1)
        conexao = ConexaoFalsa(colunas=cenario["colunas"])
        with self.assertRaisesRegex(cp.ErroCarga, "difere do DDL"):
            self.carregar(conexao)
        self.assertEqual(conexao.inseridos, {})

    def test_restricao_faltando_e_recusada(self):
        cenario = cenario_correto()
        cenario["restricoes"]["oferta_ensino"]["f"] = 1
        conexao = ConexaoFalsa(restricoes=cenario["restricoes"])
        with self.assertRaisesRegex(cp.ErroCarga, "restrições"):
            self.carregar(conexao)
        self.assertEqual(conexao.inseridos, {})

    def test_falha_no_meio_do_insert_faz_rollback(self):
        conexao = ConexaoFalsa(falhar_no_insert="oferta_ensino")
        with self.assertRaisesRegex(RuntimeError, "falha simulada"):
            self.carregar(conexao)
        self.assertEqual((conexao.commits, conexao.rollbacks), (0, 1))
        self.assertNotIn("indicador_educacional", conexao.inseridos)

    def test_validacao_pos_carga_divergente_faz_rollback(self):
        casos = {
            "contagens": lambda m: m["contagens"].update(escola=7904),
            "sem_ideb": lambda m: m.update(sem_ideb=0),
            "sem_registro_matricula": lambda m: m.update(sem_registro_matricula=717),
            "indicador_fora_de_publica_ativa": lambda m: m.update(indicador_fora_de_publica_ativa=1),
            "fks_orfas": lambda m: m["fks_orfas"].update(fk_oferta_ensino_escola=2),
            "escolas_interesse": lambda m: m["escolas_interesse"].pop(),
        }
        for chave, alterar in casos.items():
            with self.subTest(chave=chave):
                def medir(cursor, alterar=alterar):
                    medidas = copy.deepcopy(self.esperado)
                    alterar(medidas)
                    return medidas
                conexao = ConexaoFalsa()
                with self.assertRaisesRegex(cp.ErroCarga, chave):
                    self.carregar(conexao, medir)
                self.assertEqual((conexao.commits, conexao.rollbacks), (0, 1))

    def test_interrupcao_pelo_usuario_faz_rollback(self):
        def medir(cursor):
            raise KeyboardInterrupt
        conexao = ConexaoFalsa()
        with self.assertRaises(KeyboardInterrupt):
            self.carregar(conexao, medir)
        self.assertEqual((conexao.commits, conexao.rollbacks), (0, 1))

    def test_medicao_usa_apenas_consultas_de_leitura(self):
        conexao = ConexaoFalsa()
        cursor = conexao.cursor()
        silencioso(cp.medir_banco_apos_carga, cursor)
        for sql, parametros in conexao.comandos:
            self.assertTrue(sql.lstrip().startswith("SELECT"), sql)
        self.assertIn((cp.ESCOLAS_INTERESSE, cp.ANO_REFERENCIA),
                      [p for _, p in conexao.comandos if p])

    def test_erro_de_conexao_nao_expoe_credenciais(self):
        import psycopg
        erro = psycopg.OperationalError("password authentication failed: senha=Segredo123 host=x")
        with mock.patch("psycopg.connect", side_effect=erro), \
             mock.patch("getpass.getpass", return_value="Segredo123"):
            with self.assertRaises(cp.ErroCarga) as contexto:
                cp.abrir_conexao(pedir_senha=True)
        self.assertNotIn("Segredo123", str(contexto.exception))
        self.assertIsNone(contexto.exception.__cause__)
        self.assertTrue(contexto.exception.__suppress_context__)

    def test_senha_digitada_vai_so_para_o_driver(self):
        capturado = {}
        with mock.patch("psycopg.connect", side_effect=lambda **k: capturado.update(k) or "ok"), \
             mock.patch("getpass.getpass", return_value="Segredo123"):
            saida = io.StringIO()
            with contextlib.redirect_stdout(saida):
                cp.abrir_conexao(pedir_senha=True)
        self.assertEqual(capturado["password"], "Segredo123")
        self.assertEqual(capturado["dbname"], cp.BANCO)
        self.assertNotIn("Segredo123", saida.getvalue())


if __name__ == "__main__":
    unittest.main()

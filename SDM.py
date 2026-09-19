import sqlite3
import os
import sys

SPARTIALITE_DLL = r"C:\Users\carlo\anaconda3\envs\geo_env\Library\bin\mod_spatialite.dll"

class SpatialDatabaseManager:
    """
    Gerencia um banco de dados SQLite com extensão espacial (SpatiaLite).
    Fornece métodos para criar, validar e estruturar as tabelas domicilios e individuos.
    """
    
    # Estrutura esperada das tabelas (usada para validação)
    EXPECTED_TABLES = {
        'domicilios': {
            'columns': {
                'domicilio': 'INTEGER',
                'cod_setor': 'TEXT',
                'uf': 'TEXT',
                'regiao': 'TEXT',
                'municipio': 'TEXT',
                'distrito': 'TEXT',
                'subdist': 'TEXT',
                'bairro': 'TEXT',
                'aglomerado': 'TEXT',
                'localidade': 'TEXT',
                'situacao': 'TEXT',
                'fonte': 'TEXT',
                'endereco': 'TEXT',
                'tipo': 'TEXT',
                'especie': 'TEXT',
                'cls_mrdrs': 'TEXT',
                'qtd_mrdrs': 'INTEGER'
            },
            'primary_key': ['domicilio', 'cod_setor'],
            'geometry_column': ('localizacao', 4326, 'POINT')
        },
        'individuos': {
            'columns': {
                'individuo': 'INTEGER',
                'cod_setor': 'TEXT',
                'sexo': 'TEXT',
                'idade': 'INTEGER',
                'cor': 'TEXT',
                'alfabetizacao': 'TEXT',
                'tipo_domicilio': 'TEXT',
                'id_domicilio': 'INTEGER'
            },
            'primary_key': ['individuo', 'cod_setor'],
            'foreign_keys': [
                {
                    'local_cols': ['id_domicilio', 'cod_setor'],
                    'ref_table': 'domicilios',
                    'ref_cols': ['domicilio', 'cod_setor'],
                    'on_delete': 'CASCADE'
                }
            ]
        }
    }
    
    def __init__(self, db_path, spatialite_dll_path=SPARTIALITE_DLL):
        """
        Inicializa o gerenciador.
        
        Args:
            db_path (str): Caminho para o arquivo do banco de dados (.db).
            spatialite_dll_path (str, optional): Caminho para a DLL do SpatiaLite.
                Se não fornecido, tenta encontrar no ambiente Anaconda.
        """
        self.db_path = db_path
        self.spatialite_dll = spatialite_dll_path
        self._connection = None
    
    def _connect(self):
        """Abre conexão com o banco e carrega a extensão espacial."""
        if self._connection is None:
            conn = sqlite3.connect(self.db_path)
            conn.enable_load_extension(True)
            conn.load_extension(self.spatialite_dll)
            conn.execute("PRAGMA foreign_keys = ON;")
            self._connection = conn
        return self._connection
    
    def close(self):
        """Fecha a conexão ativa."""
        if self._connection:
            self._connection.close()
            self._connection = None
    
    def create_database(self):
        """
        Cria um novo banco de dados espacial (inicializa metadados SpatiaLite).
        Se o banco já existir, apenas verifica e ativa a extensão.
        """
        conn = self._connect()
        # Inicializa metadados espaciais (idempotente)
        conn.execute("SELECT InitSpatialMetadata(1)")
        conn.commit()
        print(f"✅ Banco de dados espacial criado/verificado em: {self.db_path}")
    
    def validate_database(self):
        """
        Verifica se o banco é um banco espacial SpatiaLite válido.
        
        Returns:
            bool: True se for espacial, False caso contrário.
        """
        try:
            conn = self._connect()
            # 1. Verifica versão do SpatiaLite
            versao = conn.execute("SELECT spatialite_version();").fetchone()[0]
            print(f"Versão do SpatiaLite: {versao}")
            
            versao > '5'
            print("✅ Banco de dados é um banco espacial válido.")
            return True
            
        except Exception as e:
            print(f"❌ Erro ao validar banco de dados: {e}")
            return False
    
    def check_tables(self):
        """
        Verifica se as tabelas 'domicilios' e 'individuos' existem e estão
        com a estrutura esperada (colunas, tipos, PK, FK e geometria).
        
        Returns:
            dict: Dicionário com o status de cada tabela e detalhes.
        """
        result = {
            'domicilios': {'exists': False, 'valid': False, 'errors': []},
            'individuos': {'exists': False, 'valid': False, 'errors': []}
        }
        
        conn = self._connect()
        
        for table_name, expected in self.EXPECTED_TABLES.items():
            # Verifica existência
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,)
            )
            if not cursor.fetchone():
                result[table_name]['errors'].append("Tabela não existe")
                continue
            result[table_name]['exists'] = True
            
            # Obtém estrutura atual
            cursor = conn.execute(f"PRAGMA table_info({table_name})")
            cols = cursor.fetchall()
            actual_cols = {col[1]: col[2] for col in cols}
            actual_pk = [col[1] for col in cols if col[5] > 0]
            
            # Valida colunas
            expected_cols = expected['columns']
            for col_name, col_type in expected_cols.items():
                if col_name not in actual_cols:
                    result[table_name]['errors'].append(f"Coluna '{col_name}' ausente")
                elif actual_cols[col_name].upper() != col_type:
                    result[table_name]['errors'].append(
                        f"Coluna '{col_name}' tipo esperado {col_type}, encontrado {actual_cols[col_name]}"
                    )
            
            # Valida chave primária
            if set(actual_pk) != set(expected['primary_key']):
                result[table_name]['errors'].append(
                    f"PK esperada {expected['primary_key']}, encontrada {actual_pk}"
                )
            
            # Valida geometria (se aplicável)
            if 'geometry_column' in expected:
                geo_name, srid, geo_type = expected['geometry_column']
                cursor = conn.execute(
                    "SELECT 1 FROM geometry_columns WHERE f_table_name=? AND f_geometry_column=?",
                    (table_name, geo_name)
                )
                if not cursor.fetchone():
                    result[table_name]['errors'].append(
                        f"Coluna geométrica '{geo_name}' não registrada no metadado"
                    )
                # Opcional: verifica SRID e tipo (mais complexo, pode ser feito com consultas adicionais)
            
            # Valida chave estrangeira (individuos)
            if 'foreign_keys' in expected:
                cursor = conn.execute(f"PRAGMA foreign_key_list({table_name})")
                fks = cursor.fetchall()
                # Simplificamos: verifica se existe pelo menos uma FK que referencie domicilios
                # Idealmente, deveríamos verificar cada FK definida, mas para este caso é suficiente
                found = False
                for fk in fks:
                    if fk[2] == 'domicilios':
                        found = True
                        break
                if not found:
                    result[table_name]['errors'].append("FK para domicilios não encontrada")
            
            # Se não houver erros, a tabela é válida
            if not result[table_name]['errors']:
                result[table_name]['valid'] = True
        
        # Exibe resumo
        for table, status in result.items():
            if status['valid']:
                print(f"✅ Tabela {table} está OK")
            else:
                print(f"❌ Tabela {table} com problemas: {', '.join(status['errors'])}")
                return False  # Se qualquer tabela estiver inválida, retorna False
        
        return True
    
    def create_tables(self, force=False):
        """
        Cria as tabelas domicilios e individuos com a estrutura definida.
        Se force=True, recria as tabelas (DROP e CREATE).
        Se force=False, cria apenas se não existirem.
        """
        conn = self._connect()
        conn.execute("PRAGMA foreign_keys = ON;")
        
        if force:
            # Remove tabelas existentes (cuidado com dados!)
            conn.execute("DROP TABLE IF EXISTS individuos;")
            conn.execute("DROP TABLE IF EXISTS domicilios;")
            # Remove metadados espaciais associados (opcional, mas seguro)
            conn.execute("DELETE FROM geometry_columns WHERE f_table_name='domicilios';")
        
        # Cria tabela domicilios
        conn.execute("""
        CREATE TABLE IF NOT EXISTS domicilios (
            domicilio INTEGER NOT NULL,
            cod_setor TEXT NOT NULL,
            uf TEXT,
            regiao TEXT,
            municipio TEXT,
            distrito TEXT,
            subdist TEXT,
            bairro TEXT,
            aglomerado TEXT,
            localidade TEXT,
            situacao TEXT,
            fonte TEXT,
            endereco TEXT,
            tipo TEXT,
            especie TEXT,
            cls_mrdrs TEXT,
            qtd_mrdrs INTEGER,
            PRIMARY KEY (domicilio, cod_setor)
        );
        """)
        
        # Adiciona coluna geométrica
        conn.execute("SELECT AddGeometryColumn('domicilios', 'localizacao', 4326, 'POINT', 'XY');")
        
        # Índices
        conn.execute("CREATE INDEX IF NOT EXISTS idx_domicilios_uf ON domicilios(uf);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_domicilios_municipio ON domicilios(municipio);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_domicilios_tipo ON domicilios(tipo);")
        conn.execute("SELECT CreateSpatialIndex('domicilios', 'localizacao');")
        
        # Cria tabela individuos
        conn.execute("""
        CREATE TABLE IF NOT EXISTS individuos (
            individuo INTEGER NOT NULL,
            cod_setor TEXT NOT NULL,
            sexo TEXT,
            idade INTEGER,
            cor TEXT,
            alfabetizacao TEXT,
            tipo_domicilio TEXT,
            id_domicilio INTEGER,
            PRIMARY KEY (individuo, cod_setor),
            CONSTRAINT fk_individuos_domicilios 
                FOREIGN KEY (id_domicilio, cod_setor) 
                REFERENCES domicilios(domicilio, cod_setor) 
                ON DELETE CASCADE
        );
        """)
        
        # Índices
        conn.execute("CREATE INDEX IF NOT EXISTS idx_individuos_cod_setor ON individuos(cod_setor);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_individuos_idade ON individuos(idade);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_individuos_fk ON individuos(id_domicilio, cod_setor);")
        
        conn.commit()
        print("✅ Tabelas criadas/verificadas com sucesso!")

    def insert_domicilios(self, gdf_domicilios):
        conn = self._connect()
        # Remove TODAS as colunas que são geometrias (geometry e localizacao)
        colunas_para_remover = ['geometry', 'localizacao']
        colunas_atributos = [col for col in gdf_domicilios.columns if col not in colunas_para_remover]
        df_atributos = gdf_domicilios[colunas_atributos]
        
        # 2. Insere os atributos
        df_atributos.to_sql("domicilios", conn, if_exists="append", index=False)
        
        # 3. Atualiza a geometria usando o WKT
        for idx, row in gdf_domicilios.iterrows():
            conn.execute(
                "UPDATE domicilios SET localizacao = GeomFromText(?, 4326) WHERE domicilio = ? AND cod_setor = ?",
                (row.localizacao.wkt, row['domicilio'], row['cod_setor'])
            )
        
        conn.commit()
        print(f"✅ {len(gdf_domicilios)} registros inseridos com geometria!")   

    def insert_individuos(self, df_individuos):
        conn = self._connect()
        df_individuos.to_sql("individuos", conn, if_exists="append", index=False)

        total = conn.execute("SELECT COUNT(*) FROM individuos").fetchone()[0]
        print(f"✅ {total} registros inseridos na tabela INDIVÍDUOS")

        conn.commit()

    def delete_uf_municipio(self, uf=None, municipio=None, confirmar=True):
        """
        Deleta todos os domicílios (e indivíduos em cascata) que correspondem à UF e/ou município.

        Parâmetros:
            conn: conexão SQLite (já com a extensão SpatiaLite carregada)
            uf (str, opcional): código da UF (ex: 'SP', 'RJ')
            municipio (str, opcional): nome do município (ex: 'São Paulo')
            confirmar (bool): se True, pede confirmação do usuário antes de deletar

        Retorna:
            int: número de domicílios deletados

        Exemplo:
            deletar_por_uf_municipio(conn, uf='São Paulo')
            deletar_por_uf_municipio(conn, municipio='Rio de Janeiro')
        """
        conn = self._connect()
        # Validação: pelo menos um parâmetro deve ser fornecido
        if (uf is None and municipio is None) or (uf is not None and municipio is not None):
            raise ValueError("É necessário que um dos parâmetros 'uf' ou 'municipio' seja fornecido")

        # Ativa o suporte a chaves estrangeiras (obrigatório para o CASCADE funcionar)
        conn.execute("PRAGMA foreign_keys = ON;")

        # Constrói a cláusula WHERE dinamicamente
        where_parts = []
        params = []
        if uf is not None:
            where_parts.append("uf = ?")
            params.append(uf)
        if municipio is not None:
            where_parts.append("municipio = ?")
            params.append(municipio)
        where_clause = " AND ".join(where_parts)

        # 1. Conta quantos domicílios serão afetados
        count_sql = f"SELECT COUNT(*) FROM domicilios WHERE {where_clause}"
        total_domicilios = conn.execute(count_sql, params).fetchone()[0]

        if total_domicilios == 0:
            print(f"⚠️ Nenhum domicílio encontrado para a condição: {where_clause} (parâmetros: {params})")
            return 0

        # 2. Conta quantos indivíduos serão afetados (opcional, mas útil)
        count_ind_sql = f"""
            SELECT COUNT(*) FROM individuos 
            WHERE (id_domicilio, cod_setor) IN (
                SELECT domicilio, cod_setor FROM domicilios WHERE {where_clause}
            )
        """
        total_individuos = conn.execute(count_ind_sql, params).fetchone()[0]

        print(f"\n📊 Registros encontrados:")
        print(f"   🏠 {total_domicilios} domicílios")
        print(f"   👤 {total_individuos} indivíduos (serão deletados em cascata)")

        # 3. Confirmação (se solicitada)
        if confirmar:
            resposta = input("\nDeseja realmente excluir esses registros? (s/N): ")
            if resposta.lower() != 's':
                print("❌ Operação cancelada.")
                return 0

        # 4. Executa a deleção
        try:
            delete_sql = f"DELETE FROM domicilios WHERE {where_clause}"
            conn.execute(delete_sql, params)
            conn.commit()
            print(f"\n✅ {total_domicilios} domicílios e {total_individuos} indivíduos deletados com sucesso!")
            return total_domicilios
        except Exception as e:
            conn.rollback()
            print(f"❌ Erro durante a deleção: {e}")
            return 0

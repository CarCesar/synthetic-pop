# Geração de Populações Sintéticas

Este documento apresenta as fontes de dados utilizadas e as estruturas
necessárias para a execução do algoritmo de geração de populações
sintéticas desenvolvido neste trabalho.

## Fontes dos dados

Para o desenvolvimento do algoritmo, são utilizadas bases de dados
provenientes do **IBGE**, organizadas em três grupos:

-   [Agregados](#dados-agregados)
-   [Malhas](#malhas-dos-setores-censitários)
-   [CNEFE](#cnefe)

### Dados agregados

Os dados agregados contêm informações para todos os municípios. Para sua
utilização, é necessário realizar o download e a descompactação das
seguintes tabelas:

  -----------------------------------------------------------------------------------------------
  Dados                               Arquivo
  ----------------------------------- -----------------------------------------------------------
  Alfabetização                       `Agregados_por_setores_alfabetizacao_BR.zip`

  Domicílios                          `Agregados_por_setores_caracteristicas_domicilio1_BR.zip`

  Cor ou Raça                         `Agregados_por_setores_cor_ou_raca_BR.zip`

  Demografia                          `Agregados_por_setores_demografia_BR.zip`
  -----------------------------------------------------------------------------------------------

Os arquivos estão disponíveis no [site de downloads de dados agregados
do Censo
2022](https://www.ibge.gov.br/estatisticas/downloads-estatisticas.html).

> **Observação:** entre os dados agregados, somente a tabela de
> **Demografia** passa por um tratamento prévio para resolver o
> mascaramento de dados descrito na Seção 2.1.2.1 do trabalho.

O tratamento é realizado pela função `Demografia_sem_mascara`, que
recebe a tabela original. Como esse processamento é mais lento, ele deve
ser realizado uma única vez antes da geração da população.

Portanto, sempre que a tabela de **Demografia** for mencionada na
execução do algoritmo, deve-se considerar a tabela resultante da função
`Demografia_sem_mascara`.

### Malhas dos setores censitários

As malhas dos setores censitários são específicas para o município que
será processado. Os dados estão disponíveis por estado ou para a união
de todos os estados.

Por questões de memória, o algoritmo foi desenvolvido utilizando a
versão organizada por estado.

Para a execução, deve ser utilizado o arquivo shapefile (`.shp`)
referente ao estado em que se encontra o município desejado.

Os arquivos devem estar organizados no seguinte diretório:

``` text
censo_2022/setores/shp/UF/
```

Os dados podem ser obtidos por meio da página de [downloads das malhas
dos setores censitários do
IBGE](https://www.ibge.gov.br/geociencias/organizacao-do-territorio/malhas-territoriais/).

### CNEFE

Os dados do **CNEFE --- Cadastro Nacional de Endereços para Fins
Estatísticos** apresentam um volume de dados ainda maior que as malhas,
pois concentram os endereços catalogados.

Por esse motivo, é utilizada a versão dos dados disponibilizada para
download por município.

Os arquivos devem estar no seguinte diretório:

``` text
Censo_Demografico_2022/Arquivos_CNEFE/csv/Municipio/<Estado>/
```

Os dados podem ser obtidos na página do [Censo Demográfico 2022 do
IBGE](https://www.ibge.gov.br/estatisticas/sociais/populacao/22827-censo-demografico-2022.html).

------------------------------------------------------------------------

## Estrutura do algoritmo

O algoritmo está disponível no repositório do projeto no GitHub e é
composto por duas classes e uma função auxiliar utilizada no tratamento
dos dados de Demografia.

### `SyntheticPopulation`

A classe principal do algoritmo é `SyntheticPopulation`.

Ao ser inicializada, a classe recebe os quatro caminhos correspondentes
às tabelas de dados agregados:

-   Demografia --- já tratada;
-   Alfabetização;
-   Cor ou Raça;
-   Domicílio.

Exemplo:

``` python
from SymPop import SyntheticPopulation

sympop = SyntheticPopulation(
    agg_demografia=demografia,
    agg_alfabetizacao=alfabetizacao,
    agg_cor=cor_raca,
    agg_domicilio=domicilio
)
```

#### `generate_population`

O método `generate_population` recebe:

-   o nome do município;
-   o caminho da malha referente ao estado;
-   o caminho dos dados do CNEFE.

Esse método é responsável por carregar os dados e orquestrar as etapas
internas da geração da população sintética.

Internamente, são utilizados os métodos:

-   `_get_individuos`
-   `_get_domicilios`
-   `_get_conexao`

Esses métodos sintetizam as etapas descritas na metodologia.

Ao final da execução, as entidades geradas permanecem disponíveis na
memória da classe.

#### `save_population`

O método `save_population` permite persistir a população gerada em um
banco **SpatiaLite**.

O método recebe:

-   o nome do banco de dados;
-   o parâmetro `new_database`, que indica se o banco será criado ou se
    já existem dados prévios.

Exemplo:

``` python
sympop.save_population(banco, new_database=True)
```

------------------------------------------------------------------------

## `SpatialDatabaseManager`

A classe `SpatialDatabaseManager` é responsável pelo gerenciamento do
banco espacial SQLite utilizado para armazenar os dados gerados.

Para sua utilização, é necessária a instalação da extensão
**SpatiaLite**.

No ambiente Windows, devido às particularidades de instalação da
extensão, foi utilizado diretamente no código o caminho para o
executável:

``` text
mod_spatialite.dll
```

Esse caminho precisa ser ajustado para a localização correspondente na
máquina em que o algoritmo for executado.

A classe recebe o caminho do banco de dados durante sua inicialização.

### Principais métodos

  Método                  Função
  ----------------------- ----------------------------------------------
  `create_database`       Criação de novos bancos de dados
  `create_tables`         Criação das tabelas
  `validate_database`     Validação de bancos existentes
  `check_tables`          Verificação da estrutura das tabelas
  `insert_domicilios`     Inserção dos domicílios gerados
  `insert_individuos`     Inserção dos indivíduos gerados
  `delete_uf_municipio`   Exclusão dos dados de um estado ou município

O método `delete_uf_municipio` não está diretamente ligado à classe
principal, mas aproveita a estrutura de cascata entre as tabelas para
simplificar a exclusão dos dados de um estado ou município da base.

------------------------------------------------------------------------

## Exemplo de execução

O código a seguir apresenta um exemplo de geração da população sintética
para o município de **Oiapoque, no Amapá**:

``` python
from SymPop import SyntheticPopulation

domicilio = 'Agregados_por_setores_caracteristicas_domicilio1_BR.csv'
demografia = 'Agregados_por_setores_demografia_BR_preenchido.csv'
alfabetizacao = 'Agregados_por_setores_alfabetizacao_BR.csv'
cor_raca = 'Agregados_por_setores_cor_ou_raca_BR.csv'

malha = 'AP_setores_CD2022.shp'
cnefe = '1600501_OIAPOQUE.csv'
municipio = 'Oiapoque'
banco = 'oiapoque.db'

sympop = SyntheticPopulation(
    agg_demografia=demografia,
    agg_alfabetizacao=alfabetizacao,
    agg_cor=cor_raca,
    agg_domicilio=domicilio
)

sympop.generate_population(municipio, malha, cnefe)

sympop.save_population(banco, new_database=True)
```

### Execução para múltiplos municípios

Para gerar populações sintéticas para mais de um município, os comandos
de geração e persistência podem ser executados recursivamente.

Na **primeira execução**, o parâmetro deve ser:

``` python
new_database=True
```

Nas execuções seguintes, quando o banco já possuir dados previamente
inseridos, deve ser utilizado:

``` python
new_database=False
```

Dessa forma, novos municípios podem ser adicionados ao banco existente
sem criar um novo banco a cada execução.

------------------------------------------------------------------------

## Estrutura dos dados utilizados

De forma resumida, a execução do algoritmo depende dos seguintes
componentes:

``` text
Dados agregados
├── Demografia
├── Alfabetização
├── Cor ou Raça
└── Domicílio

Dados específicos do município
├── Malha dos setores censitários
└── CNEFE

Algoritmo
├── SyntheticPopulation
│   ├── _get_individuos
│   ├── _get_domicilios
│   ├── _get_conexao
│   ├── generate_population
│   └── save_population
│
└── SpatialDatabaseManager
    ├── create_database
    ├── create_tables
    ├── validate_database
    ├── check_tables
    ├── insert_domicilios
    ├── insert_individuos
    └── delete_uf_municipio
```

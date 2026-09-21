import numpy as np
import geopandas as gpd
import pandas as pd
from tqdm import tqdm
from shapely.geometry import Polygon, Point
from shapely.vectorized import contains  # use contains_xy se estiver com Shapely >= 2.0

from SDM import SpatialDatabaseManager

def define_geo_points(polygon,num_required):
    minx, miny, maxx, maxy = polygon.bounds
    area_bbox = (maxx - minx) * (maxy - miny)
    area_polygon = polygon.area

    # Gerar pontos vetorialmente
    batch_size = int(num_required /(area_polygon/area_bbox))  # margem para garantir cobertura
    a = 2.326  # z para 99%
    batch_size = int((num_required + a /2 + a*(num_required + a/4)**0.5)/(area_polygon/area_bbox))  # margem para garantir cobertura
    x = np.random.uniform(minx, maxx, batch_size)
    y = np.random.uniform(miny, maxy, batch_size)
    
    # Filtrar vetorialmente os pontos dentro do polígono
    mask = contains(polygon, x, y)  # use contains_xy se estiver com Shapely >= 2.0
    valid_coords = np.column_stack((x[mask], y[mask]))

    # Selecionar os primeiros 55.000 pontos válidos
    selected_coords = valid_coords[:int(num_required)]
    
    if len(valid_coords) < num_required:
        print(batch_size, len(valid_coords))
        selected_coords = define_geo_points(polygon,num_required)
    
    return selected_coords

def get_age(v):
    try:
        idade = int(v[0])*10
        if v[-1] == 'a':
            idade += np.random.randint(5)
        elif v[-1] == 'b':
            idade += 5 + np.random.randint(5)
        else:
            idade += np.random.randint(10)
        
        if v == '8':
            idade = 80 + int(np.random.exponential(scale=3.5))
    except Exception as e:
        print(e, '- ', v)
        idade = np.nan
    return idade

class SyntheticPopulation:
    def __init__(self,agg_demografia, agg_alfabetizacao, agg_cor, agg_domicilio):
        demografia = pd.read_csv(agg_demografia, sep=';')
        demografia['COD_setor'] = demografia['CD_setor'].astype('str')
        self.agg_demografia = demografia
        self.agg_alfabetizacao = pd.read_csv(agg_alfabetizacao, sep=';')
        self.agg_cor = pd.read_csv(agg_cor, sep=';')
        AGR_DOM = pd.read_csv(agg_domicilio, sep=';')
        AGR_DOM = AGR_DOM.loc[~AGR_DOM.iloc[:, 1:].eq('X').all(axis=1)].reset_index(drop=True)
        cods = [str(a) for a in AGR_DOM.CD_setor]
        AGR_DOM = AGR_DOM.replace('X', '1').astype(int)
        AGR_DOM['COD_setor'] = cods#[str(a) for a in AGR_DOM.CD_setor]
        AGR_DOM = AGR_DOM.drop(columns=['CD_setor'])
        self.agg_domicilio = AGR_DOM
        self.setores = None
        self.CNEFE = None

        self.simulados_df = None
        self.pessoas = None
        self.domicilios = None

    def _get_individuos(self):
        dic_cor = {'V01392':'M0_A', 'V01393':'M0_B', 'V01394':'M0_C', 'V01395':'M0_D', 'V01396':'M0_E',
        'V01402':'F0_A', 'V01403':'F0_B', 'V01404':'F0_C', 'V01405':'F0_D', 'V01406':'F0_E',
        'V01372':'a__A', 'V01373':'a__B', 'V01374':'a__C', 'V01375':'a__D', 'V01376':'a__E'}

        cor = self.agg_cor[['CD_SETOR']+ list(dic_cor.keys())].rename(columns = dic_cor)

        dic = {'V00657':'a1b_A','V00658':'a1b_B','V00659':'a1b_C','V00660':'a1b_D','V00661':'a1b_E',
        'V00662':'a2a_A','V00663':'a2a_B','V00664':'a2a_C','V00665':'a2a_D','V00666':'a2a_E',
        'V00667':'a2b_A','V00668':'a2b_B','V00669':'a2b_C','V00670':'a2b_D','V00671':'a2b_E',
        'V00672':'a3a_A','V00673':'a3a_B','V00674':'a3a_C','V00675':'a3a_D','V00676':'a3a_E',
        'V00677':'a3b_A','V00678':'a3b_B','V00679':'a3b_C','V00680':'a3b_D','V00681':'a3b_E',
        'V00682':'a4a_A','V00683':'a4a_B','V00684':'a4a_C','V00685':'a4a_D','V00686':'a4a_E',
        'V00687':'a4b_A','V00688':'a4b_B','V00689':'a4b_C','V00690':'a4b_D','V00691':'a4b_E',
        'V00692':'a5a_A','V00693':'a5a_B','V00694':'a5a_C','V00695':'a5a_D','V00696':'a5a_E',
        'V00697':'a5b_A','V00698':'a5b_B','V00699':'a5b_C','V00700':'a5b_D','V00701':'a5b_E',
        'V00702':'a6a_A','V00703':'a6a_B','V00704':'a6a_C','V00705':'a6a_D','V00706':'a6a_E',
        'V00707':'a6b_A','V00708':'a6b_B','V00709':'a6b_C','V00710':'a6b_D','V00711':'a6b_E',
        'V00712':'a7_A','V00713':'a7_B','V00714':'a7_C','V00715':'a7_D','V00716':'a7_E',
        'V00717':'a8_A','V00718':'a8_B','V00719':'a8_C','V00720':'a8_D','V00721':'a8_E'}

        def get_list_age_race(aa, lista):
            return [b for a in [[a]*aa.loc[0,a] for a in lista] for b in a]

        alf = self.agg_alfabetizacao[['CD_setor'] + list(dic.keys())].rename(columns = dic)

        dic_alf = {'V00870':'g1_A_S','V00871':'g1_A_N','V00872':'g1_B_S','V00873':'g1_B_N','V00874':'g1_C_S','V00875':'g1_C_N','V00876':'g1_D_S','V00877':'g1_D_N','V00878':'g1_E_S','V00879':'g1_E_N',
        'V00880':'g2_A_S','V00881':'g2_A_N','V00882':'g2_B_S','V00883':'g2_B_N','V00884':'g2_C_S','V00885':'g2_C_N','V00886':'g2_D_S','V00887':'g2_D_N','V00888':'g2_E_S','V00889':'g2_E_N',
        'V00890':'g3_A_S','V00891':'g3_A_N','V00892':'g3_B_S','V00893':'g3_B_N','V00894':'g3_C_S','V00895':'g3_C_N','V00896':'g3_D_S','V00897':'g3_D_N','V00898':'g3_E_S','V00899':'g3_E_N'}

        alf2 = self.agg_alfabetizacao[['CD_setor']+ list(dic_alf.keys())].rename(columns = dic_alf)

        setores_ = self.setores.merge(self.agg_demografia, left_on='CD_SETOR', right_on = 'COD_setor', how= 'inner')

        listagem_total = []
        for a in setores_.index:
            s = setores_.iloc[a]
            cod_setor = s['CD_SETOR']
            listagem = []
            for valor in ['M0a','M0b','M1a','M1b','M2a','M2b','M3','M4','M5','M6','M7',
                        'F0a','F0b','F1a','F1b','F2a','F2b','F3','F4','F5','F6','F7']:
                listagem.extend([{'COD_setor': cod_setor, 'sexo': valor[0], 'faixa_etaria': valor[1:], 
                                'fe_2':np.nan, 'cor':np.nan, 'alfabetizacao': 'I' if valor[1:] in ['0a', '0b', '1a'] else 'S', 
                                'tipo_domicilio':np.nan,'id_domicilio':np.nan}]*int(s[valor]))

            listagem = np.random.choice(listagem, size = len(listagem), replace= False)

            listagem_total.extend(listagem)

        df = pd.DataFrame(listagem_total)

        for i_s in setores_.index:
            s = setores_.iloc[i_s]
            cod_setor = s['CD_SETOR']
            
            ## COR e Idade mais detalhada(15 anos ou mais)
            colunas_com_X = list(alf.columns[alf[alf.CD_setor == int(cod_setor)].eq('X').any()])
            aa = alf[alf.CD_setor == int(cod_setor)][list(dic.values())].replace('X', '2').astype('int').reset_index(drop=True)

            for v in ['a1b','a2a','a2b','a3','a4','a5','a6','a7']:
                valor = int(s[v])
                if valor == 0:
                    continue
                if v[-1] in ['a','b']:
                    lista= [v+'_A',v+'_B',v+'_C',v+'_D',v+'_E']
                elif v == 'a7':
                    lista = ['a7_A','a7_B','a7_C','a7_D','a7_E','a8_A','a8_B','a8_C','a8_D','a8_E']
                else:
                    lista = [v+'a_A',v+'a_B',v+'a_C',v+'a_D',v+'a_E', v+'b_A',v+'b_B',v+'b_C',v+'b_D',v+'b_E']
                ab = get_list_age_race(aa,lista)
                while valor > len(ab):
                    ab.append(v + '_I')
                if valor < len(ab):
                    x = [x for x in colunas_com_X if x in ab]
                    x = list(np.random.choice(x, size = len(x), replace= False))
                    for a in x:
                        if valor < len(ab):
                            ab.remove(a)
                            colunas_com_X.remove(a)

                ab = list(np.random.choice(ab, size = valor, replace= False))

                df.loc[df['COD_setor'].isin([cod_setor]) & df.faixa_etaria.isin([v[1:]]),['fe_2','cor']] = [[a[1:-2],a[-1]] for a in ab]

            ## COR (!5 anos ou menos)
            quantos_os = len(df.loc[df['COD_setor'].isin([cod_setor]) & df.faixa_etaria.isin(['0a','0b']) & df.sexo.isin(['M']),['cor']])
            quantos_as = len(df.loc[df['COD_setor'].isin([cod_setor]) & df.faixa_etaria.isin(['0a','0b']) & df.sexo.isin(['F']),['cor']])
            quantos_adol = len(df.loc[df['COD_setor'].isin([cod_setor]) & df.faixa_etaria.isin(['1a']),['cor']])

            ## Meninos até 10 anos
            colunas_com_X = list(cor.columns[cor[alf.CD_setor == int(cod_setor)].eq('X').any()])
            aa = cor[alf.CD_setor == int(cod_setor)][list(dic_cor.values())].replace('X', '2').astype('int').reset_index(drop=True)
            ab = get_list_age_race(aa,['M0_A','M0_B','M0_C','M0_D','M0_E'])
            while quantos_os > len(ab):
                ab.append('M0_I')
            if quantos_os < len(ab):
                x = [x for x in colunas_com_X if x in ab]
                x = list(np.random.choice(x, size = len(x), replace= False))
                for a in x:
                    if quantos_os < len(ab):
                        ab.remove(a)

            ab = list(np.random.choice(ab, size = quantos_os, replace= False))
            df.loc[df['COD_setor'].isin([cod_setor]) & df.faixa_etaria.isin(['0a','0b']) & df.sexo.isin(['M']),'cor'] = [a[-1] for a in ab]

            memoria = [a[-1] for a in ab]

            ## Meninas até 10 anos
            ab = get_list_age_race(aa,['F0_A','F0_B','F0_C','F0_D','F0_E'])
            while quantos_as > len(ab):
                ab.append('F0_I')
            if quantos_as < len(ab):
                x = [x for x in colunas_com_X if x in ab]
                x = list(np.random.choice(x, size = len(x), replace= False))
                for a in x:
                    if quantos_as < len(ab):
                        ab.remove(a)

            ab = list(np.random.choice(ab, size = quantos_as, replace= False))
            df.loc[df['COD_setor'].isin([cod_setor]) & df.faixa_etaria.isin(['0a','0b']) & df.sexo.isin(['F']),'cor'] = [a[-1] for a in ab]

            memoria+= [a[-1] for a in ab]

            # crianças entre 10 e 14 anos
            ab = [a[-1] for a in get_list_age_race(aa,['a__A','a__B','a__C','a__D','a__E'])]
            for a in memoria:
                if a in ab: ### Idealmente não deveria existir, e pode causar pequeno disturbio nos dados, mas a não utilização causara custo computacional demasiadamente caro.
                    ab.remove(a)
            while quantos_adol > len(ab):
                ab.append('I')
            if quantos_adol < len(ab):
                x = [x[-1] for x in colunas_com_X if x[0] in 'a']
                x = list(np.random.choice(x, size = len(x), replace= False))
                for a in x:
                    if quantos_adol < len(ab):
                        if a in ab:
                            ab.remove(a)

            ab = list(np.random.choice(ab, size = quantos_adol, replace= False))
            df.loc[df['COD_setor'].isin([cod_setor]) & df.faixa_etaria.isin(['1a']),'cor'] = ab

            ### Analfabetismo
            lista = list(dic_alf.values())
            aa  = alf2[alf2.CD_setor == int(cod_setor)][lista].replace('X', '2').astype('int').reset_index(drop=True)
            map_fe = {'g1':['1b','2a','2b'], 'g2':['3','4','5'], 'g3':['6','7']}
            for a in lista[1::2]:
                t0 = sum(df['COD_setor'].isin([cod_setor]) & df.faixa_etaria.isin(map_fe[a[:2]]) & df.cor.isin([a[3]]))
                t1 = aa.loc[0,a[:-1]+'S']
                tamanho_amostra = min(aa.loc[0,a], t0) # evita erro de ter menos gente que o número de analfabetos
                if tamanho_amostra == 2:
                    tamanho_amostra = max(t0-t1,1)
                    # print(t0,t1,tamanho_amostra)
                df.loc[df[
                        df['COD_setor'].isin([cod_setor]) & 
                        df.faixa_etaria.isin(map_fe[a[:2]]) & 
                        df.cor.isin([a[3]])].sample(tamanho_amostra).index,'alfabetizacao'] = 'N'
                # try:
                #     df.loc[df[
                #         df['COD_setor'].isin([cod_setor]) & 
                #         df.faixa_etaria.isin(map_fe[a[:2]]) & 
                #         df.cor.isin([a[3]])].sample(aa.loc[0,a]).index,'alfabetizacao'] = 'N'
                # except:
                #     if aa.loc[0,a] == 2:
                #         df.loc[df[
                #         df['COD_setor'].isin([cod_setor]) & 
                #         df.faixa_etaria.isin(map_fe[a[:2]]) & 
                #         df.cor.isin([a[3]])].sample(1).index,'alfabetizacao'] = 'N'

        df['fe_2'] = df['fe_2'].fillna(df['faixa_etaria'])
        df.fe_2 = df.fe_2.apply(get_age)
        df = df.rename(columns = {'fe_2':'idade'})
        

        return df

    def _get_domicilios(self):

        AGR_DOM = self.agg_domicilio.copy()

        setores = self.setores.copy()
        CNEFE = self.CNEFE.copy() if self.CNEFE is not None else None

        simulados = []

        # Pernamentes

        agr_per = AGR_DOM[['COD_setor','V00017', 'V00018', 'V00019', 'V00020', 'V00021', 'V00022', 'V00023', 'V00024', 'V00025', 'V00026',
                'V00047','V00048','V00049','V00001']].rename(columns={'V00017':'m1', 'V00018':'m2', 'V00019':'m3', 'V00020':'m4', 
                                                                                        'V00021':'m5', 'V00022':'m6', 'V00023':'m7', 'V00024':'m8', 'V00025':'m9', 'V00026':'m10',
                                                                                        'V00047':'casa','V00048':'vila','V00049':'ap','V00001':'total'})
        agr_per['diff'] = agr_per.total-agr_per.casa-agr_per.vila-agr_per.ap
        agr_per['sem_num_moradores'] = agr_per.total-agr_per.m1-agr_per.m2-agr_per.m3-agr_per.m4-agr_per.m5-agr_per.m6-agr_per.m7-agr_per.m8-agr_per.m9-agr_per.m10
        agr_per

        lista_domicilios_permanentes_df = []

        s = setores.merge(agr_per, left_on='CD_SETOR', right_on='COD_setor', how='inner')

        for idx_setores in tqdm(range(len(s))):
            domicilios_permanentes = []
            for especie in [('casa',101), ('vila',102), ('ap',103)]:
                cod_setor = s.loc[idx_setores].CD_SETOR
                num_domicilios = s.loc[idx_setores][especie[0]]
                geo = s.loc[idx_setores].geometry
                
                if num_domicilios == 0:
                    continue

                dic_default = {'cod_setor': cod_setor, 'tipo': 'permanente', 'especie': especie[0]}

                CNEFE_setor = CNEFE[(CNEFE.COD_setor == cod_setor) & (CNEFE.COD_ESPECIE == 1) & (CNEFE.COD_TIPO_ESPECI == especie[1])]
                if len(CNEFE_setor) > 0:
                    CNEFE_setor['within'] = CNEFE_setor.apply(
                        lambda row: row['ponto'].within(geo),
                        axis=1
                    )
                    CNEFE_setor = CNEFE_setor[CNEFE_setor.within == True]

                lista_CNEFE = [dic_default | {'fonte': 'CNEFE', 'endereco': x} for x in CNEFE_setor.COD_UNICO_ENDERECO.tolist()]
                if len(lista_CNEFE) >= num_domicilios:
                    indices_selecionados = np.random.choice(len(lista_CNEFE), size=num_domicilios, replace=False)
                    domicilios_permanentes = domicilios_permanentes + [lista_CNEFE[i] for i in indices_selecionados]
                else:
                    lista_faltante = define_geo_points(geo, num_domicilios - len(lista_CNEFE))
                    simulados = simulados + [dic_default | {'id': x, 'ponto':lista_faltante[x]} for x in range(len(lista_faltante))]
                    lista_final = lista_CNEFE + [dic_default | {'fonte': 'simulados', 'endereco': x} for x in range(len(lista_faltante))]
                    indices_selecionados = np.random.choice(len(lista_final), size=num_domicilios, replace=False)
                    domicilios_permanentes = domicilios_permanentes + [lista_final[i] for i in indices_selecionados]

            domicilios_permanentes_df = pd.DataFrame(domicilios_permanentes)

            num_diff = s.loc[idx_setores]['diff']
            if num_diff > 0:

                dic_default = {'cod_setor': cod_setor, 'tipo': 'permanente', 'especie': 'outros'}

                CNEFE_setor = CNEFE[
                    (~CNEFE.COD_UNICO_ENDERECO.isin(domicilios_permanentes_df[domicilios_permanentes_df['fonte'] == 'CNEFE'].endereco.to_list())) & 
                    (CNEFE.COD_ESPECIE == 1) & 
                    (CNEFE.COD_setor == cod_setor)]
                
                if len(CNEFE_setor) > 0:
                    CNEFE_setor['within'] = CNEFE_setor.apply(
                            lambda row: row['ponto'].within(geo),
                            axis=1
                        )
                    CNEFE_setor = CNEFE_setor[CNEFE_setor.within == True]
                lista_CNEFE = [dic_default | {'fonte': 'CNEFE', 'endereco': x} for x in CNEFE_setor.COD_UNICO_ENDERECO.tolist()]
                if len(lista_CNEFE) >= num_diff:
                    indices_selecionados = np.random.choice(len(lista_CNEFE), size=num_diff, replace=False)
                    novos = [lista_CNEFE[i] for i in indices_selecionados]
                else:
                    lista_faltante = define_geo_points(geo, num_diff - len(lista_CNEFE))
                    simulados = simulados + [dic_default | {'id': x, 'ponto':lista_faltante[x]} for x in range(len(lista_faltante))]
                    lista_final = lista_CNEFE + [dic_default | {'fonte': 'simulados', 'endereco': x} for x in range(len(lista_faltante))]
                    indices_selecionados = np.random.choice(len(lista_final), size=num_diff, replace=False)
                    novos = [lista_final[i] for i in indices_selecionados]

                domicilios_permanentes_df = pd.DataFrame(domicilios_permanentes + novos)

            # quantidade de moradores por domicilio
            lista_num_moradores = []
            for num_moradores in ['m1', 'm2', 'm3', 'm4', 'm5', 'm6', 'm7', 'm8', 'm9', 'm10', 'sem_num_moradores']:
                lista_num_moradores += [num_moradores]*s.loc[idx_setores][num_moradores]
            

            domicilios_permanentes_df['num_moradores'] = np.random.choice(lista_num_moradores, size=len(domicilios_permanentes_df), replace=False)

            lista_domicilios_permanentes_df.append(domicilios_permanentes_df)


        # Improvisados

        agr_imp = AGR_DOM[['COD_setor','V00027', 'V00028', 'V00029', 'V00030', 'V00031', 'V00032', 'V00033', 'V00034', 'V00035', 'V00036',
        'V00053','V00054','V00055','V00056','V00057','V00058','V00002']].rename(columns={'V00027':'m1', 'V00028':'m2', 'V00029':'m3', 'V00030':'m4', 
                                                                        'V00031':'m5', 'V00032':'m6', 'V00033':'m7', 'V00034':'m8', 'V00035':'m9', 'V00036':'m10',
                                                                        'V00053':'tenda','V00054':'estabelecimento','V00055':'natural','V00056':'publico',
                                                                        'V00057':'n_residencial', 'V00058':'veiculo', 'V00002':'total'})
        agr_imp['diff'] = agr_imp.total-agr_imp.tenda-agr_imp.estabelecimento-agr_imp.natural-agr_imp.publico-agr_imp.n_residencial-agr_imp.veiculo
        agr_imp['sem_num_moradores'] = agr_imp.total-agr_imp.m1-agr_imp.m2-agr_imp.m3-agr_imp.m4-agr_imp.m5-agr_imp.m6-agr_imp.m7-agr_imp.m8-agr_imp.m9-agr_imp.m10

        lista_domicilios_improvisados_df = []

        s = setores.merge(agr_imp, left_on='CD_SETOR', right_on='COD_setor', how='inner')

        for idx_setores in tqdm(range(len(s))):

            cod_setor = s.loc[idx_setores].CD_SETOR
            num_domicilios = s.loc[idx_setores]['total']
            geo = s.loc[idx_setores].geometry

            dic_default = {'cod_setor': cod_setor, 'tipo': 'improvisado', 'especie': ''}

            lista_especies = []
            for especie in ('tenda', 'estabelecimento', 'natural', 'publico', 'n_residencial', 'veiculo','diff'):
                especie_name = 'outros' if especie == 'diff' else especie
                lista_especies += [especie_name]*s.loc[idx_setores][especie]

            lista_faltante = define_geo_points(geo, num_domicilios)
            simulados = simulados + [dic_default | {'especie':lista_especies[x], 'id': x, 'ponto':lista_faltante[x]} for x in range(len(lista_faltante))]
            lista_selecionados = [dic_default | {'especie':lista_especies[x], 'fonte': 'simulados', 'endereco': x} for x in range(len(lista_faltante))]

            domicilios_improvisados_df = pd.DataFrame(lista_selecionados)
            lista_num_moradores = []
            for num_moradores in ['m1', 'm2', 'm3', 'm4', 'm5', 'm6', 'm7', 'm8', 'm9', 'm10', 'sem_num_moradores']:
                lista_num_moradores += [num_moradores]*s.loc[idx_setores][num_moradores]
            domicilios_improvisados_df['num_moradores'] = np.random.choice(lista_num_moradores, size=len(domicilios_improvisados_df), replace=False)

            lista_domicilios_improvisados_df.append(domicilios_improvisados_df)


        # Coletivos

        agr_col = AGR_DOM[['COD_setor','V00037', 'V00038', 'V00039', 'V00040', 'V00041', 'V00042', 'V00043', 'V00044', 'V00045', 'V00046',
        'V00059','V00060','V00061','V00062','V00063','V00064','V00065','V00066','V00067','V00068','V00069','V00003']].rename(
            columns={'V00037':'m1', 'V00038':'m2', 'V00039':'m3', 'V00040':'m4', 'V00041':'m5', 'V00042':'m6', 'V00043':'m7', 'V00044':'m8', 'V00045':'m9', 'V00046':'m10',
                    'V00059':'asilo','V00060':'hotel','V00061':'alojamento','V00062':'penitenciaria', 'V00063':'outros_domicilios', 'V00064':'albergue', 
                    'V00065':'abrigo','V00066':'clinica_psi','V00067':'orfanato','V00068':'internacao_menores','V00069':'quartel','V00003':'total'})

        agr_col['diff'] = agr_col.total-agr_col.asilo-agr_col.hotel-agr_col.alojamento-agr_col.penitenciaria-agr_col.outros_domicilios-agr_col.albergue-agr_col.abrigo-agr_col.clinica_psi-agr_col.orfanato-agr_col.internacao_menores-agr_col.quartel
        agr_col['sem_num_moradores'] = agr_col.total-agr_col.m1-agr_col.m2-agr_col.m3-agr_col.m4-agr_col.m5-agr_col.m6-agr_col.m7-agr_col.m8-agr_col.m9-agr_col.m10

        lista_domicilios_coletivos_df = []

        s = setores.merge(agr_col, left_on='CD_SETOR', right_on='COD_setor', how='inner')

        for idx_setores in tqdm(range(len(s))):

            cod_setor = s.loc[idx_setores].CD_SETOR
            num_domicilios = s.loc[idx_setores]['total']
            geo = s.loc[idx_setores].geometry

            dic_default = {'cod_setor': cod_setor, 'tipo': 'coletivo', 'especie': ''}

            CNEFE_setor = CNEFE[(CNEFE.COD_setor == cod_setor) & (CNEFE.COD_ESPECIE == 2)]
            if len(CNEFE_setor) > 0:
                CNEFE_setor['within'] = CNEFE_setor.apply(
                        lambda row: row['ponto'].within(geo),
                        axis=1
                    )
                CNEFE_setor = CNEFE_setor[CNEFE_setor.within == True]

            lista_especies = []
            for especie in ('asilo', 'hotel', 'alojamento', 'penitenciaria', 'outros_domicilios', 'albergue', 'abrigo', 'clinica_psi', 'orfanato', 'internacao_menores', 'quartel', 'diff'):
                especie_name = 'outros' if especie == 'diff' else especie
                lista_especies += [especie_name]*s.loc[idx_setores][especie]
            lista_especies = np.random.choice(lista_especies, size=num_domicilios, replace=False)

            lista_CNEFE = [dic_default | {'fonte': 'CNEFE', 'endereco': x} for x in CNEFE_setor.COD_UNICO_ENDERECO.tolist()]
            if len(lista_CNEFE) >= num_domicilios:
                indices_selecionados = np.random.choice(len(lista_CNEFE), size=num_domicilios, replace=False)
                lista_selecionados = [lista_CNEFE[i] for i in indices_selecionados]
            else:
                lista_faltante = define_geo_points(geo, num_domicilios - len(lista_CNEFE))
                simulados = simulados + [dic_default | {'especie': lista_especies[x], 'id': x, 'ponto':lista_faltante[x]} for x in range(len(lista_faltante))]
                # aqui, a ordem importa, pois para o especie é chave primariado simulados
                lista_selecionados =[dic_default | {'especie': lista_especies[x], 'fonte': 'simulados', 'endereco': x} for x in range(len(lista_faltante))] + lista_CNEFE
        

            domicilios_coletivos_df = pd.DataFrame(lista_selecionados)

            domicilios_coletivos_df['especie'] = lista_especies
            lista_num_moradores = []
            for num_moradores in ['m1', 'm2', 'm3', 'm4', 'm5', 'm6', 'm7', 'm8', 'm9', 'm10', 'sem_num_moradores']:
                lista_num_moradores += [num_moradores]*s.loc[idx_setores][num_moradores]
            domicilios_coletivos_df['num_moradores'] = np.random.choice(lista_num_moradores, size=len(domicilios_coletivos_df), replace=False)

            lista_domicilios_coletivos_df.append(domicilios_coletivos_df)
        
        self.simulados_df = pd.DataFrame(simulados)
        domicilios = pd.concat(lista_domicilios_permanentes_df + lista_domicilios_improvisados_df + lista_domicilios_coletivos_df, ignore_index=True)

        return domicilios

    def _get_conexao(self, domicilios, pessoas):

        domicilios['num_moradores_int'] = domicilios['num_moradores'].replace({'sem_num_moradores': 'm1'}).apply(lambda x: np.nan if pd.isna(x) else int(x[1:]) )
        domicilios['mais_moradores'] = domicilios['num_moradores'].isin(['sem_num_moradores','m10'])
        domicilios = domicilios.reset_index().rename(columns={'index':'id_domicilio'})
        
        agr_dom_pes = self.agg_domicilio[['COD_setor','V00008','V00009','V00010','V00011','V00012','V00013', 'V00014','V00015','V00016']].rename(
            columns={'V00008':'per_crianca','V00009':'imp_crianca','V00010':'col_crianca','V00011':'per_homem','V00012':'imp_homem','V00013':'col_homem',
                    'V00014':'per_mulher','V00015':'imp_mulher','V00016':'col_mulher'})

        setores_pes = self.setores[['CD_SETOR']].merge(agr_dom_pes, left_on='CD_SETOR', right_on='COD_setor', how='inner')

        pessoas['COD_setor'] = pessoas.COD_setor.astype(str)

        for index, s in tqdm(setores_pes.iterrows()):
            for tipo in ['permanente', 'improvisado', 'coletivo']:
                tip = tipo[:3]
                num_crianca = s[f'{tip}_crianca']
                num_homem = s[f'{tip}_homem']
                num_mulher = s[f'{tip}_mulher']

                cod_setor = s['COD_setor']
                index_crianca = pessoas[(pessoas['COD_setor'] == cod_setor) & (pessoas['faixa_etaria'].isin(['0a','0b'])) & (pessoas['tipo_domicilio'].isna())].iloc[:num_crianca].index
                pessoas.loc[index_crianca, 'tipo_domicilio'] = tipo

                num_homem -= sum((pessoas.tipo_domicilio == tipo) & (pessoas.sexo == 'M') & (pessoas['COD_setor'] == cod_setor))
                num_mulher -= sum((pessoas.tipo_domicilio == tipo) & (pessoas.sexo == 'F') & (pessoas['COD_setor'] == cod_setor))

                index_homem = pessoas[(pessoas['COD_setor'] == cod_setor) & (pessoas.sexo == 'M') & (~pessoas['faixa_etaria'].isin(['0a','0b'])) & (pessoas['tipo_domicilio'].isna())].iloc[:num_homem].index
                pessoas.loc[index_homem, 'tipo_domicilio'] = tipo

                index_mulher = pessoas[(pessoas['COD_setor'] == cod_setor) & (pessoas.sexo == 'F') & (~pessoas['faixa_etaria'].isin(['0a','0b'])) & (pessoas['tipo_domicilio'].isna())].iloc[:num_mulher].index
                pessoas.loc[index_mulher, 'tipo_domicilio'] = tipo

                domicilios_setor = domicilios[(domicilios.cod_setor == cod_setor) & (domicilios.tipo == tipo)]

                #primeiro integrante de cada domicilio
                id_domicilio_list = domicilios_setor.id_domicilio.tolist()
                index_primeiro_morador = pessoas[(pessoas['COD_setor'] == cod_setor) & (pessoas['tipo_domicilio'] == tipo) & (~pessoas['faixa_etaria'].isin(['0a','0b']))].iloc[:len(id_domicilio_list)].index
                pessoas.loc[index_primeiro_morador, 'id_domicilio'] = np.random.choice(id_domicilio_list, size = len(index_primeiro_morador), replace=False)

                #domicilios com numero de moradores definidos
                ids = []
                for row in domicilios_setor.itertuples():
                    ids.extend([row.id_domicilio]*(row.num_moradores_int-1))
                index_outros_moradores = pessoas[(pessoas['COD_setor'] == cod_setor) & (pessoas['tipo_domicilio'] == tipo) & (pessoas['id_domicilio'].isna())].iloc[:len(ids)].index
                pessoas.loc[index_outros_moradores, 'id_domicilio'] = np.random.choice(ids, size=len(index_outros_moradores), replace=False)

                #não definidos
                index_outros_moradores = pessoas[(pessoas['COD_setor'] == cod_setor) & (pessoas['tipo_domicilio'] == tipo) & (pessoas['id_domicilio'].isna())].index
                list_dom = domicilios_setor.id_domicilio[domicilios_setor.mais_moradores].to_list()
                if list_dom != []:
                    pessoas.loc[index_outros_moradores, 'id_domicilio'] =np.random.choice(list_dom, size=len(index_outros_moradores), replace=True)

        domicilios['COD_ESPECIE'] = (domicilios.tipo=='coletivo') + 1
        domicilios = domicilios.merge(
                pessoas.groupby('id_domicilio').size().reset_index(name='num_moradores_simulacao'), left_on='id_domicilio', right_on='id_domicilio', how='left'   
            ).merge(self.setores[['CD_SETOR','SITUACAO','NM_UF','NM_MUN','NM_DIST','NM_SUBDIST','NM_BAIRRO','NM_AGLOM','NM_RGINT']],
                        left_on='cod_setor', right_on='CD_SETOR', how='left').drop( columns=['CD_SETOR','num_moradores_int','mais_moradores']       
            ).merge(self.CNEFE[['COD_ESPECIE','COD_UNICO_ENDERECO','DSC_LOCALIDADE','ponto']], left_on=['COD_ESPECIE','endereco'], right_on=['COD_ESPECIE','COD_UNICO_ENDERECO'], how='left'
            ).drop(columns=['COD_ESPECIE','COD_UNICO_ENDERECO']
            ).merge(self.simulados_df, left_on=['cod_setor','endereco','tipo','especie'], right_on=['cod_setor','id','tipo','especie'], how='left', suffixes=('', '_simulado')
            ).drop(columns=['id'])
        domicilios.loc[domicilios['ponto'].isna(), 'ponto'] = [Point(xy) for xy in domicilios[domicilios['ponto'].isna()]['ponto_simulado'].tolist()]
        domicilios.loc[domicilios['fonte']=='simulados', 'endereco'] = [np.nan]*domicilios['fonte'].isin(['simulados']).sum()
        domicilios = domicilios.drop(columns=['ponto_simulado'])

        domicilios = domicilios.rename(columns={ 'id_domicilio':'domicilio',
            'SITUACAO':'situacao', 'NM_UF':'uf', 'NM_MUN':'municipio', 'NM_DIST':'distrito', 'NM_SUBDIST':'subdist',
            'NM_BAIRRO':'bairro', 'NM_AGLOM':'aglomerado', 'NM_RGINT':'regiao', 'DSC_LOCALIDADE':'localidade', 
            'num_moradores':'cls_mrdrs','num_moradores_simulacao':'qtd_mrdrs', 'ponto':'localizacao'})
        domicilios['cls_mrdrs'] = domicilios['cls_mrdrs'].replace({'sem_num_moradores': 'indef'})

        domicilios = domicilios[['domicilio','cod_setor','uf','regiao','municipio','distrito','subdist','bairro','aglomerado',
                    'localidade','situacao','fonte', 'endereco','tipo','especie','cls_mrdrs','qtd_mrdrs','localizacao']]

        domicilios = gpd.GeoDataFrame(domicilios, geometry='localizacao', crs='EPSG:4326')

        pessoas.drop(columns='faixa_etaria', inplace=True)
        pessoas.reset_index(inplace=True)
        pessoas.rename(columns={'index': 'individuo'}, inplace=True)
        pessoas.rename(columns={'COD_setor': 'cod_setor'}, inplace=True)
        pessoas = pessoas.dropna(subset=['id_domicilio']).reset_index(drop=True)

        self.individuos = pessoas
        self.domicilios = domicilios

        print('DOMICILIOS E INDIVIDUOS GERADOS COM SUCESSO!')

    def generate_population(self, municipio, malha, cnefe, seed = 97):

        np.random.seed(seed) 
        setores = gpd.read_file(malha)
        self.setores = setores[setores['NM_MUN']== municipio]
        print('MALHA CARREGADA COM SUCESSO!', len(self.setores), 'setores encontrados.')

        self.individuos = self._get_individuos()
        print('INDIVIDUOS GERADOS COM SUCESSO!')

        CNEFE = pd.read_csv(cnefe, sep = ';')
        CNEFE['COD_setor'] = [a[:-1] for a in CNEFE.COD_SETOR]
        CNEFE['ponto'] = gpd.points_from_xy(CNEFE['LONGITUDE'], CNEFE['LATITUDE'], crs='EPSG:4326')
        self.CNEFE = CNEFE
        print('CNEFE CARREGADO COM SUCESSO!')

        self.domicilios = self._get_domicilios()
        print('DOMICILIOS GERADOS COM SUCESSO!')

        self._get_conexao(domicilios = self.domicilios.copy(), pessoas = self.individuos.copy())


    def save_population(self, databasePath, new_database):
        db = SpatialDatabaseManager(databasePath)
        if new_database:
            db.create_database()
            db.create_tables()
        else:
            val1 = db.validate_database()
            if not val1:
                raise ValueError('Database is not valid. Please check the database before saving the population.')
            val2 = db.check_tables()
            if not val2:
                raise ValueError('Tables are not valid. Please check the tables before saving the population.')
        
        db.insert_domicilios(self.domicilios)
        db.insert_individuos(self.individuos)
        db.close()

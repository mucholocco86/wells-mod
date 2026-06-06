####################################################################
####            Sistema do Menu Universal do Wells v2.0          ####
####                       Modificado por Wells                 ####
####               Processador de Expressões e AST              ####
####################################################################

init -997 python:
    import re
    import ast as _ast

    ##################################################################
    #               CLASSE DE EXPRESSÕES DO WELLS                    #
    ##################################################################

    class WellsExpressionParser:
        """Analisa strings de expressões Python para extrair variáveis e valores"""

        def __init__(self):
            # Expressões regulares para capturar atribuições e operações matemáticas comuns
            self.assignment_re = re.compile(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*(=|\+=|-=|\*=|\/=)\s*(.*)$')
            self.inc_dec_re = re.compile(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*(\+\+|--)$')
            self.call_re = re.compile(r'^([a-zA-Z_][a-zA-Z0-9_\.]*)\s*\(.*\)$')

        def parse_string(self, expr_str):
            """Analisa uma linha de código em string e retorna uma lista de consequências"""
            consequences = []
            if not expr_str:
                return consequences

            expr_str = expr_str.strip()
            if not expr_str or expr_str.startswith('#'):
                return consequences

            # Tenta encontrar atribuições normais ou incrementos (+=, -=, etc)
            match = self.assignment_re.match(expr_str)
            if match:
                var_name, op, val_str = match.groups()
                var_name = var_name.strip()
                val_str = val_str.strip()

                if op == '=':
                    ctype = ConsequenceType.ASSIGN
                    if val_str.lower() in ['true', 'false']:
                        ctype = ConsequenceType.BOOLEAN
                    consequences.append(WellsConsequence(ctype, var_name, val_str))
                elif op == '+=':
                    consequences.append(WellsConsequence(ConsequenceType.INCREASE, var_name, val_str))
                elif op == '-=':
                    consequences.append(WellsConsequence(ConsequenceType.DECREASE, var_name, val_str))
                return consequences

            # Tenta encontrar operadores de incremento curto (style ++ ou --)
            match = self.inc_dec_re.match(expr_str)
            if match:
                var_name, op = match.groups()
                if op == '++':
                    consequences.append(WellsConsequence(ConsequenceType.INCREASE, var_name, '1'))
                elif op == '--':
                    consequences.append(WellsConsequence(ConsequenceType.DECREASE, var_name, '1'))
                return consequences

            # Tenta encontrar chamadas de função direta
            match = self.call_re.match(expr_str)
            if match:
                func_name = match.group(1)
                if not any(skip in func_name for skip in ['renpy.', 'config.', 'style.']):
                    consequences.append(WellsConsequence(ConsequenceType.FUNCTION, func_name, ''))
                return consequences

            return consequences
        def parse_ast_node(self, node):
            """Analisa de forma recursiva um nó da árvore AST do Python para extrair lógicas"""
            consequences = []
            if node is None:
                return consequences

            try:
                # Gerencia nós de atribuição direta: ex: x = valor
                if isinstance(node, _ast.Assign):
                    for target in node.targets:
                        if isinstance(target, _ast.Name):
                            var_name = target.id
                            value = self._safe_unparse(node.value)
                            
                            ctype = ConsequenceType.ASSIGN
                            if value in ['True', 'False']:
                                ctype = ConsequenceType.BOOLEAN
                                
                            consequences.append(WellsConsequence(ctype, var_name, value))
                            
                # Gerencia nós de atribuição calculada: ex: x += 1 ou x -= 5
                elif isinstance(node, _ast.AugAssign):
                    if isinstance(node.target, _ast.Name):
                        var_name = node.target.id
                        value = self._safe_unparse(node.value)
                        op_class = node.op.__class__.__name__
                        
                        if op_class == 'Add':
                            consequences.append(WellsConsequence(ConsequenceType.INCREASE, var_name, value))
                        elif op_class == 'Sub':
                            consequences.append(WellsConsequence(ConsequenceType.DECREASE, var_name, value))
                            
                # Gerencia chamadas de funções lógicas internas do jogo
                elif isinstance(node, _ast.Call):
                    func_name = self._safe_unparse(node.func)
                    if func_name and not any(s in func_name for s in ['renpy.', 'config.', 'style.']):
                        consequences.append(WellsConsequence(ConsequenceType.FUNCTION, func_name, ''))
                        
                # Varre os nós filhos recursivamente caso seja uma estrutura de bloco complexa
                if hasattr(node, 'body') and isinstance(node.body, list):
                    for sub_node in node.body:
                        consequences.extend(self.parse_ast_node(sub_node))
                        
                if hasattr(node, 'orelse') and isinstance(node.orelse, list):
                    for sub_node in node.orelse:
                        consequences.extend(self.parse_ast_node(sub_node))
                        
            except Exception as e:
                wells_log.debug(f"Erro ao processar nó AST interno do Python: {e}", "PARSER_EXPRESSAO")

            return consequences

        def _safe_unparse(self, node):
            """Converte de forma segura um nó AST do Python de volta para texto legível"""
            if node is None:
                return "?"
            try:
                # Se a versão do Python do Ren'Py tiver suporte nativo ao unparse (Python 3.9+)
                if hasattr(_ast, 'unparse'):
                    res = _ast.unparse(node).strip()
                    return res[:40]
                # Fallback de segurança para versões mais antigas de motores gráficos
                if isinstance(node, _ast.Name):
                    return node.id
                elif isinstance(node, _ast.Constant):
                    return str(node.value)
                elif isinstance(node, _ast.Num):
                    return str(node.n)
                elif isinstance(node, _ast.Str):
                    return node.s
            except:
                pass
            return "?"

    # Instancia o analisador de expressões de roteiro global sob o seu nick
    wells_expression_parser = WellsExpressionParser()
    ##################################################################
    #              CLASSE DO PROCESSADOR DO WELLS                    #
    ##################################################################

    class WellsProcessor:
        """Gerencia a extração, cache e otimização das consequências de escolhas"""

        def __init__(self):
            # Inicializa contadores internos para estatísticas e auditoria de velocidade
            self._processed_count = 0
            self._cache_hits = 0
            self._miss_count = 0

        def process_choice(self, menu_node, choice_index, match_info):
            """Processa um botão de escolha específico dentro do nó do menu do jogo"""
            if not menu_node or not hasattr(menu_node, 'items'):
                return []

            strategy = match_info.get('strategy', 'exact')
            offset = match_info.get('offset', 0)

            # Ajusta o alinhamento de índice com base nas estratégias de localização do WellsMenuFinder
            if strategy == 'skip_first':
                ast_idx = choice_index + 1
            else:
                ast_idx = choice_index + offset

            if ast_idx >= len(menu_node.items):
                wells_log.debug(f"Índice da AST ({ast_idx}) fora dos limites das opções ({len(menu_node.items)})", "PROCESSADOR")
                return []

            choice_item = menu_node.items[ast_idx]

            # No motor Ren'Py, o contêiner do item de escolha é uma tupla estrutural: (texto, condição, bloco)
            if not choice_item or len(choice_item) < 3:
                return []

            block = choice_item[2] # Recupera o bloco de instruções de roteiro vinculado a este botão
            if not block:
                return []

            # Cria uma chave única de identificação para o sistema de cache e otimização de velocidade
            filename = getattr(menu_node, 'filename', 'desconhecido')
            linenumber = getattr(menu_node, 'linenumber', 0)
            cache_key = f"{filename}_{linenumber}_{ast_idx}"

            # Tenta ler os dados salvos direto do cache global para manter o jogo rápido e fluido
            cached_consequences = wells_consequence_cache.get(cache_key)
            if cached_consequences is not None:
                self._cache_hits += 1
                return cached_consequences

            self._miss_count += 1

            # Executa a varredura pesada do bloco usando o analisador estrutural de roteiro
            try:
                consequences = wells_analyzer.analyze_block(block)
                self._processed_count += 1

                # Aplica as regras de filtragem e otimização de nomes de variáveis do Wells
                filtered_consequences = self._filter_and_optimize(consequences)

                # Salva os resultados limpos no cache global com a sua marca
                wells_consequence_cache.set(cache_key, filtered_consequences)
                return filtered_consequences

            except Exception as e:
                wells_log.error(f"Erro ao processar as consequências da opção {choice_index}: {e}", "PROCESSADOR")
                return []
        def _filter_and_optimize(self, consequences):
            """Filtra, limpa e remove as consequências irrelevantes ou ocultadas do mod"""
            if not consequences:
                return []

            filtered = []
            seen = set() # Estrutura auxiliar para rastrear e eliminar dicas duplicadas idênticas

            for cons in consequences:
                # Remove itens vazios ou sem nome de variável válido
                if not cons or not cons.variable:
                    continue

                # Cria uma assinatura única para o controle de duplicados
                signature = (cons.type, str(cons.variable), str(cons.value))
                if signature in seen:
                    continue

                # Aplica os filtros de nomes baseados nas configurações persistentes do Wells
                if self._should_hide_variable(str(cons.variable)):
                    continue

                # Aplica os filtros de tipos de dados (Aumento, Salto, Funções, etc) ativos na tela do menu
                if not self._is_type_enabled(cons.type):
                    continue

                # Se passar em todas as travas e validações de segurança, adiciona na lista limpa
                seen.add(signature)
                filtered.append(cons)

            # Reclassifica dinamicamente os tipos de variáveis caso pertençam a relacionamentos ou status
            for cons in filtered:
                self._enrich_consequence_type(cons)

            return filtered

        def _should_hide_variable(self, var_name):
            """Verifica de forma lógica se o nome de uma variável deve ser escondido do jogador"""
            name_filters = persistent.wells_name_filters
            if not name_filters:
                return False

            # Regra de Prioridade Máxima: Se o desenvolvedor ou jogador forçou a exibição da variável
            if var_name in name_filters.get('important_vars', []):
                return False

            # Verifica se o nome da variável bate com a lista de prefixos customizados para sempre exibir
            for prefix in name_filters.get('custom_show', []):
                if prefix and var_name.startswith(prefix):
                    return False

            # Filtro 1: Oculta variáveis nativas do sistema que começam com sublinhado (ex: _window)
            if name_filters.get('hide_underscore', True) and var_name.startswith('_'):
                return True

            # Filtro 2: Oculta chamadas ou propriedades vinculadas ao próprio motor Ren'Py
            if name_filters.get('hide_renpy', True) and (var_name.startswith('renpy.') or var_name.startswith('renpy_')):
                return True

            # Filtro 3: Oculta variáveis de configurações globais de engines
            if name_filters.get('hide_config', False) and var_name.startswith('config.'):
                return True

            # Filtro 4: Oculta variáveis armazenadas nos escopos internos persistentes ou de store
            if name_filters.get('hide_store', True) and var_name.startswith('store.'):
                return True

            # Filtro 5: Varre a lista de prefixos customizados que o jogador escolheu ocultar
            for prefix in name_filters.get('custom_hide', []):
                if prefix and var_name.startswith(prefix):
                    return True

            return False
        def _is_type_enabled(self, type_name):
            """Valida se o tipo de consequência está ativo para exibição nos filtros do menu"""
            filters = persistent.wells_filters
            if not filters:
                return True

            # Mapeia os tipos internos do Wells para as chaves do dicionário de filtros salvos
            if type_name in [ConsequenceType.INCREASE, ConsequenceType.DECREASE]:
                return filters.get('variables', True)
            elif type_name == ConsequenceType.ASSIGN:
                return filters.get('variables', True)
            elif type_name == ConsequenceType.BOOLEAN:
                return filters.get('flags', True)
            elif type_name in [ConsequenceType.JUMP, ConsequenceType.CALL, ConsequenceType.RETURN]:
                return filters.get('flow', True)
            elif type_name == ConsequenceType.CONDITION:
                return filters.get('conditions', True)
            elif type_name == ConsequenceType.FUNCTION:
                return filters.get('functions', True)
            elif type_name in [ConsequenceType.RELATIONSHIP]:
                return filters.get('relationships', True)
            elif type_name in [ConsequenceType.STAT]:
                return filters.get('stats', True)
            elif type_name == ConsequenceType.UNKNOWN:
                return filters.get('unknown', False)

            return True

        def _enrich_consequence_type(self, cons):
            """Analisa o nome da variável para categorizá-la de forma visual como afeto ou atributo"""
            if cons.type not in [ConsequenceType.INCREASE, ConsequenceType.DECREASE, ConsequenceType.ASSIGN]:
                return

            var_lower = str(cons.variable).lower()

            # Padrões textuais para identificar variáveis de relacionamento e afeto
            relationship_keywords = [
                'love', 'trust', 'affection', 'relationship', 'romance', 'points_carol',
                'friendship', 'respect', 'loyalty', 'affinity', 'favour', 'attraction',
                're_carol', 'points_carolina', 'love_carol', 'trust_carol'
            ]

            # Padrões textuais para identificar atributos gerais do personagem ou status do jogo
            stat_keywords = [
                'points', 'money', 'health', 'reputation', 'stat', 'score', 'cash',
                'strength', 'intelligence', 'charisma', 'wisdom', 'energy', 'sanity',
                'exp', 'level', 'gold', 'skills', 'intellect', 'willpower'
            ]

            # Se bater com os prefixos de afeto, altera o tipo visual para exibir o ícone de coração (♥)
            if any(kw in var_lower for kw in relationship_keywords):
                cons.type = ConsequenceType.RELATIONSHIP
                cons.metadata = ConsequenceType.get_metadata(ConsequenceType.RELATIONSHIP)
                return

            # Se bater com status, altera o tipo visual para exibir o ícone de estrela (★)
            if any(kw in var_lower for kw in stat_keywords):
                cons.type = ConsequenceType.STAT
                cons.metadata = ConsequenceType.get_metadata(ConsequenceType.STAT)
                return
    ##################################################################
    #            PROCESSADOR PROFUNDO DE AST DO WELLS                #
    ##################################################################

    class WellsDeepASTProcessor:
        """Processador avançado para analisar nós e estruturas profundas da árvore AST"""

        def __init__(self, analyzer_instance):
            self.analyzer = analyzer_instance
            self._depth = 0

        def extract_from_node(self, node, source_line=0):
            """Extrai as consequências de um nó AST complexo do Python de forma recursiva"""
            consequences = []
            if node is None:
                return consequences

            try:
                # Gerencia desestruturação ou atribuições múltiplas (ex: x, y = 1, 2)
                if isinstance(node, _ast.Assign):
                    for target in node.targets:
                        if isinstance(target, (_ast.Tuple, _ast.List)):
                            consequences.extend(self._process_tuple_assignment(target, node.value, source_line))
                        elif isinstance(target, _ast.Attribute):
                            # Atribuição de propriedade de objeto: ex: player.stats.love = 5
                            prop_path = self._build_attribute_path(target)
                            if prop_path and not prop_path.startswith('_'):
                                value = wells_expression_parser._safe_unparse(node.value)
                                consequences.append(WellsConsequence(
                                    ConsequenceType.ASSIGN, prop_path, value, source_line=source_line
                                ))

                # Gerencia operações aritméticas incrementais em propriedades de objetos (ex: player.love += 1)
                elif isinstance(node, _ast.AugAssign):
                    if isinstance(node.target, _ast.Attribute):
                        prop_path = self._build_attribute_path(node.target)
                        if prop_path and not prop_path.startswith('_'):
                            value = wells_expression_parser._safe_unparse(node.value)
                            op_class = node.op.__class__.__name__
                            
                            if op_class == 'Add':
                                consequences.append(WellsConsequence(
                                    ConsequenceType.INCREASE, prop_path, value, source_line=source_line
                                ))
                            elif op_class == 'Sub':
                                consequences.append(WellsConsequence(
                                    ConsequenceType.DECREASE, prop_path, value, source_line=source_line
                                ))

            except Exception as e:
                wells_log.debug(f"Erro no processamento profundo de nó AST: {e}", "PROCESSADOR_PROFUNDO")

            return consequences

        def _build_attribute_path(self, node):
            """Monta o caminho textual completo de um atributo de objeto (ex: objeto.propriedade)"""
            try:
                if isinstance(node, _ast.Name):
                    return node.id
                elif isinstance(node, _ast.Attribute):
                    value_path = self._build_attribute_path(node.value)
                    if value_path:
                        return f"{value_path}.{node.attr}"
                    return node.attr
            except:
                pass
            return ""
        def _process_tuple_assignment(self, target_node, value_node, source_line):
            """Processa atribuições múltiplas desestruturadas em tuplas ou listas do Python"""
            consequences = []
            try:
                # Extrai os nomes das variáveis alvos da tupla
                targets = []
                for elt in target_node.elts:
                    if isinstance(elt, _ast.Name):
                        targets.append(elt.id)
                    elif isinstance(elt, _ast.Attribute):
                        targets.append(self._build_attribute_path(elt))
                    else:
                        targets.append(None)

                # Extrai os valores correspondentes que serão atribuídos
                values = []
                if isinstance(value_node, (_ast.Tuple, _ast.List)):
                    for elt in value_node.elts:
                        values.append(wells_expression_parser._safe_unparse(elt))
                else:
                    # Fallback caso os valores venham de uma função ou objeto único
                    unparsed_val = wells_expression_parser._safe_unparse(value_node)
                    values = [f"{unparsed_val}[{i}]" for i in range(len(targets))]

                # Une os alvos aos seus respectivos valores e gera as consequências limpas
                for i, var_name in enumerate(targets):
                    if not var_name or i >= len(values):
                        continue
                        
                    val_str = values[i]
                    ctype = ConsequenceType.ASSIGN
                    if val_str.lower() in ['true', 'false']:
                        ctype = ConsequenceType.BOOLEAN
                        
                    consequences.append(WellsConsequence(
                        ctype, var_name, val_str, source_line=source_line
                    ))
            except Exception as e:
                wells_log.debug(f"Erro ao desestruturar atribuição múltipla em tupla: {e}", "PROCESSADOR_PROFUNDO")

            return consequences

        def analyze_ast_conditional(self, node, source_line=0):
            """Analisa estruturas condicionais profundas em blocos puramente Python do jogo"""
            consequences = []
            if not isinstance(node, _ast.If):
                return consequences

            try:
                # Extrai o texto da condição lógica testada
                cond_text = wells_expression_parser._safe_unparse(node.test)
                if len(cond_text) > 35:
                    cond_text = cond_text[:32] + "..."

                # Varre recursivamente o bloco interno executado caso a condição seja verdadeira
                sub_cons = []
                if hasattr(node, 'body') and isinstance(node.body, list):
                    for body_node in node.body:
                        sub_cons.extend(self.extract_from_node(body_node, source_line))

                if sub_cons:
                    consequences.append(WellsConsequence(
                        ConsequenceType.CONDITION, f"if {cond_text}", str(len(sub_cons)),
                        source_line=source_line, sub_consequences=sub_cons
                    ))
                    # Adiciona alterações de alta relevância encontradas no bloco para a lista principal
                    for sub in sub_cons:
                        if sub.type in [ConsequenceType.INCREASE, ConsequenceType.DECREASE, ConsequenceType.RELATIONSHIP, ConsequenceType.STAT]:
                            consequences.append(sub)

            except Exception as e:
                wells_log.debug(f"Erro ao processar bloco condicional Python profundo: {e}", "PROCESSADOR_PROFUNDO")

            return consequences
        def _generate_signature_hash(self, source_code):
            """Gera uma assinatura hash MD5 única para otimização de busca de strings de código"""
            if not source_code:
                return ""
            try:
                # Trata strings em formatos binários ou normais para evitar quebras de codificação UTF-8
                if isinstance(source_code, str):
                    code_bytes = source_code.encode('utf-8', errors='ignore')
                else:
                    code_bytes = bytes(source_code)
                return hashlib.md5(code_bytes).hexdigest()
            except:
                # Fallback simples de texto caso o módulo de criptografia hashlib esteja bloqueado
                return str(hash(source_code))

    # Criação oficial das instâncias globais dos processadores de código usando o seu nick
    wells_processor = WellsProcessor()
    wells_deep_ast_processor = WellsDeepASTProcessor(wells_processor)

    # Registro informativo emitido ao console de desenvolvimento do Ren'Py
    wells_log.info("Processador avançado de consequências carregado com sucesso", "INICIALIZAÇÃO")
    print(f"[WELLS] Módulo Wells Processor acoplado com sucesso - Quebra-cabeça montado!")

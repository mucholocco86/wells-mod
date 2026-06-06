####################################################################
####            Sistema do Menu Universal do Wells v2.0          ####
####                       Modificado por Wells                 ####
####################################################################
#
# WELLS 2.0 - Reescrita completa com recursos aprimorados:
# - Análise profunda da AST com extração completa de consequências
# - Detecção inteligente de menu usando contexto de execução
# - Rastreamento e previsão de variáveis em tempo real
# - Interface moderna com animações e temas visuais
# - Modos de proteção contra spoiler da história
# - Histórico de escolhas e estatísticas do jogador
# - Otimizações de desempenho com cache inteligente
#
####################################################################

init -1000 python:
    # Espaço de configuração do sistema do Wells
    class WellsConfig:
        """Contêiner de Configuração do Wells"""
        VERSION = "2.0.0"
        DEBUG = False
        DEVELOPER = True
        
        # Configurações de Cache (para otimização de velocidade)
        MAX_MENU_CACHE = 500
        MAX_CONSEQUENCE_CACHE = 300
        CACHE_CLEANUP_THRESHOLD = 0.8
        
        # Configurações de Análise de Código
        MAX_RECURSION_DEPTH = 10
        MAX_CONSEQUENCES_PER_CHOICE = 50
        ANALYZE_NESTED_CONDITIONALS = True
        
        # Configurações de Exibição Padrão
        DEFAULT_TEXT_SIZE = 25
        DEFAULT_MAX_DISPLAY = 3
        
    # Instancia o objeto de configuração global com o seu nick
    wells_config = WellsConfig()

init -999:
    # Definição dos valores padrões das variáveis persistentes do seu mod
    default persistent.wells_enabled = True
    default persistent.wells_text_size = 25
    default persistent.wells_max_consequences = 3
    default persistent.wells_show_all = True
    default persistent.wells_spoiler_mode = False
    default persistent.wells_highlight_best = True
    default persistent.wells_theme = "modern"
    default persistent.wells_full_text = False         # Mostra o texto completo sem cortes
    default persistent.wells_hide_dialogue = True      # Oculta dicas de diálogos Say/TranslateSay
    
    # Filtros de Tipos de Dados a serem exibidos nas escolhas
    default persistent.wells_filters = {
        'variables': True,      # Mudanças de variáveis (+= -= =)
        'conditions': True,     # Condições do jogo (If/elif/else)
        'flow': True,           # Fluxo de roteiro (Jump/call/return)
        'functions': True,      # Chamadas de funções do Python
        'flags': True,          # Interruptores lógicos (Sinalizadores Booleanos)
        'relationships': True,   # Variáveis de relacionamento e afeto
        'stats': True,          # Alterações de atributos/atributos gerais
        'unknown': False        # Tipos desconhecidos capturados
    }
    
    # Filtros baseados em nomes de variáveis (para ocultar lógicas internas do jogo)
    default persistent.wells_name_filters = {
        'hide_underscore': True,
        'hide_renpy': True,
        'hide_config': False,
        'hide_store': True,
        'hide_internal': True,
        'custom_hide': [],      # Lista de prefixos customizados para esconder
        'custom_show': [],      # Lista de prefixos customizados para sempre mostrar (prioridade)
        'important_vars': []    # Variáveis marcadas como importantes pelo jogador
    }
    
    # Histórico de Escolhas Permanentes
    default persistent.wells_choice_history = []
    default persistent.wells_max_history = 100
    
    # Painel Acumulador de Estatísticas
    default persistent.wells_stats = {
        'menus_analyzed': 0,
        'choices_made': 0,
        'consequences_shown': 0,
        'session_start': None
    }

init -998 python:
    # Importação de bibliotecas nativas e de otimização necessárias para o motor do mod
    import collections
    import collections.abc
    import weakref
    import time as _time
    import re
    import ast as _ast
    import hashlib

    ##################################################################
    #                    SISTEMA DE LOGS DO WELLS                    #
    ##################################################################
    
    class WellsLogger:
        """Sistema de registro e depuração de mensagens (logs) do Wells"""
        
        _instance = None
        
        def __new__(cls):
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
        
        def __init__(self):
            if self._initialized:
                return
            self._initialized = True
            self._log_buffer = []            # Buffer para armazenar as mensagens em memória
            self._max_buffer = 1000          # Limite máximo de linhas do buffer
            self._enabled = wells_config.DEBUG
            
        def log(self, message, level="INFO", category="GERAL"):
            """Registra uma mensagem com um nível e uma categoria específica"""
            if not self._enabled and level != "ERRO":
                return
                
            timestamp = _time.strftime("%H:%M:%S")
            entry = f"[WELLS {timestamp}] [{level}] [{category}] {message}"
            
            self._log_buffer.append(entry)
            if len(self._log_buffer) > self._max_buffer:
                self._log_buffer = self._log_buffer[-self._max_buffer//2:]
            
            if wells_config.DEBUG:
                print(entry)
        
        def debug(self, message, category="DEPURAÇÃO"):
            self.log(message, "DEPURAÇÃO", category)
            
        def info(self, message, category="INFO"):
            self.log(message, "INFO", category)
            
        def warn(self, message, category="AVISO"):
            self.log(message, "AVISO", category)
            
        def error(self, message, category="ERRO"):
            self.log(message, "ERRO", category)
            
        def get_logs(self, count=50):
            return self._log_buffer[-count:]
            
        def clear(self):
            self._log_buffer.clear()
    
    # Instancia o registrador de logs global usando o seu nick
    wells_log = WellsLogger()
    
    ##################################################################
    #                    SISTEMA DE CACHE DO WELLS                   #
    ##################################################################
    
    class WellsCache:
        """Cache LRU com limpeza automatizada e coleta de estatísticas de velocidade"""
        
        def __init__(self, max_size=500, name="cache"):
            self.name = name
            self.max_size = max_size
            self._cache = {}
            self._access_times = {}
            self._hit_count = 0
            self._miss_count = 0
            
        def get(self, key, default=None):
            """Recupera um item do cache de otimização"""
            if key in self._cache:
                self._access_times[key] = _time.time()
                self._hit_count += 1
                return self._cache[key]
            self._miss_count += 1
            return default
            
        def set(self, key, value):
            """Salva um item no cache aplicando uma limpeza automática se estiver cheio"""
            # Segurança contra loops e acúmulos na limpeza de cache
            if len(self._cache) >= self.max_size * wells_config.CACHE_CLEANUP_THRESHOLD:
                self._cleanup()
            
            self._cache[key] = value
            self._access_times[key] = _time.time()
            
        def has(self, key):
            return key in self._cache
            
        def remove(self, key):
            if key in self._cache:
                del self._cache[key]
                del self._access_times[key]
                
        def _cleanup(self):
            """Remove os registros mais antigos e menos acessados da memória"""
            if len(self._cache) < self.max_size // 2:
                return
                
            sorted_items = sorted(self._access_times.items(), key=lambda x: x[1])
            remove_count = len(self._cache) // 4
            
            for i in range(min(remove_count, len(sorted_items))):
                key = sorted_items[i][0]
                if key in self._cache:
                    del self._cache[key]
                if key in self._access_times:
                    del self._access_times[key]
                    
            wells_log.debug(f"O cache '{self.name}' foi limpo: removidos {remove_count} itens", "CACHE")
            
        def clear(self):
            self._cache.clear()
            self._access_times.clear()
            
        def stats(self):
            total = self._hit_count + self._miss_count
            hit_rate = (self._hit_count / total * 100) if total > 0 else 0
            return {
                'tamanho': len(self._cache),
                'tamanho_maximo': self.max_size,
                'acertos': self._hit_count,
                'erros': self._miss_count,
                'taxa_acerto': f"{hit_rate:.1f}%"
            }
    
    # Criação das instâncias globais de cache com o seu nick
    wells_menu_cache = WellsCache(wells_config.MAX_MENU_CACHE, "menu")
    wells_consequence_cache = WellsCache(wells_config.MAX_CONSEQUENCE_CACHE, "consequencia")
    wells_node_cache = WellsCache(200, "no_codigo")

    ##################################################################
    #                TIPOS DE CONSEQUÊNCIA DO WELLS                  #
    ##################################################################
    
    class ConsequenceType:
        """Enumeração e metadados de todos os tipos de consequências de escolhas"""
        
        INCREASE = "aumento"
        DECREASE = "diminuicao"
        ASSIGN = "atribuicao"
        BOOLEAN = "booleano"
        JUMP = "salto"
        CALL = "chamada"
        RETURN = "retorno"
        CONDITION = "condicao"
        FUNCTION = "funcao"
        CODE = "codigo"
        RELATIONSHIP = "relacionamento"
        STAT = "atributo"
        FLAG = "sinalizador"
        UNKNOWN = "desconhecido"
        
        # Dicionário de Metadados (Ícones visíveis, cores hexadecimais e prioridade na tela)
        METADATA = {
            "aumento": {"icon": "+", "color": "#4f4", "priority": 10},
            "diminuicao": {"icon": "-", "color": "#f44", "priority": 10},
            "atribuicao": {"icon": "=", "color": "#44f", "priority": 5},
            "booleano": {"icon": "●", "color": "#4af", "priority": 6},
            "salto": {"icon": "→", "color": "#f84", "priority": 3},
            "chamada": {"icon": "⇒", "color": "#8f4", "priority": 4},
            "retorno": {"icon": "←", "color": "#f48", "priority": 2},
            "condicao": {"icon": "?", "color": "#ff8", "priority": 1},
            "funcao": {"icon": "ƒ", "color": "#af4", "priority": 5},
            "codigo": {"icon": "◇", "color": "#ccc", "priority": 0},
            "relacionamento": {"icon": "♥", "color": "#f4a", "priority": 15},
            "atributo": {"icon": "★", "color": "#fa4", "priority": 12},
            "sinalizador": {"icon": "◆", "color": "#4fa", "priority": 8},
            "desconhecido": {"icon": "?", "color": "#888", "priority": -1}
        }
        
        @classmethod
        def get_metadata(cls, type_name):
            return cls.METADATA.get(type_name, cls.METADATA["desconhecido"])
    
    ##################################################################
    #                CLASSE DE CONSEQUÊNCIA DO WELLS                 #
    ##################################################################
    
    class WellsConsequence:
        """Representa uma única consequência extraída de uma opção de escolha"""
        
        def __init__(self, ctype, variable, value="", display="", source_line=0, confidence=1.0, sub_consequences=None, branch_consequences=None):
            self.type = ctype
            self.variable = variable
            self.value = value
            self.display = display or f"{variable}"
            self.source_line = source_line
            self.confidence = confidence
            self.metadata = ConsequenceType.get_metadata(ctype)
            self.sub_consequences = sub_consequences or []  # Para blocos condicionais: lista linear
            # branch_consequences: dicionário no formato {"if condicao": [cons], "else": [cons]}
            self.branch_consequences = branch_consequences or {}
            
        def __repr__(self):
            return f"<Consequence {self.type}: {self.variable}={self.value}>"
            
        def __eq__(self, other):
            if not isinstance(other, WellsConsequence):
                return False
            return (self.type == other.type and 
                    self.variable == other.variable and 
                    self.value == other.value)
                    
        def __hash__(self):
            return hash((self.type, self.variable, self.value))
            
        def format(self, style="compacto"):
            """Formata a consequência de forma amigável para exibição visual na tela"""
            meta = self.metadata
            icon = meta["icon"]
            
            if style == "compacto":
                if self.type in ["aumento", "diminuicao"]:
                    if self.value and self.value != "1":
                        return f"{icon}{self.variable} ({self.value})"
                    return f"{icon}{self.variable}"
                elif self.type == "atribuicao":
                    val = self.value[:15] + "..." if len(str(self.value)) > 15 else self.value
                    return f"{self.variable}={val}"
                elif self.type == "booleano":
                    return f"{self.variable}={self.value}"
                elif self.type in ["salto", "chamada"]:
                    return f"{icon} {self.variable}"
                elif self.type == "retorno":
                    return f"{icon}"
                elif self.type == "condicao":
                    cond = str(self.variable)[:25]
                    return f"{icon} {cond}"
                else:
                    return self.display[:30]
            
            elif style == "detalhado":
                return f"{icon} {self.type.upper()}: {self.variable} = {self.value}"
            
            return self.display
            
        def get_priority(self):
            """Calcula a prioridade de exibição (valores maiores aparecem primeiro no topo)"""
            base_priority = self.metadata["priority"]
            
            # Varre palavras chaves para dar um bônus de importância para afinidades ou atributos
            var_lower = str(self.variable).lower()
            relationship_keywords = ['love', 'trust', 'affection', 'relationship', 'faith', 
                                'friendship', 'respect', 'loyalty', 're_']
            stat_keywords = ['points', 'money', 'health', 'reputation', 'stat', 'score',
                        'strength', 'intelligence', 'charisma']
            
            for kw in relationship_keywords:
                if kw in var_lower:
                    return base_priority + 20
                    
            for kw in stat_keywords:
                if kw in var_lower:
                    return base_priority + 15
                    
            return base_priority

    ##################################################################
    #                ANALISADOR AST DO WELLS                         #
    ##################################################################
    
    class WellsAnalyzer:
        """Analisador de Árvore de Sintaxe Abstrata (AST) para extração de consequências"""
        
        # Exceções de controle de fluxo nativas do Ren'Py que NUNCA devem ser capturadas pelo mod
        CONTROL_EXCEPTIONS = (
            renpy.game.FullRestartException,
            renpy.game.UtterRestartException,
            renpy.game.QuitException,
            renpy.game.JumpException,
            renpy.game.JumpOutException,
            renpy.game.CallException,
            renpy.game.EndReplay,
            renpy.game.ParseErrorException,
            KeyboardInterrupt
        )
        
        # Instruções nativas do Ren'Py que o mod ignora (são apenas visuais, áudio ou diálogos)
        SKIP_STATEMENTS = (
            'Say', 'Scene', 'Show', 'Hide', 'With', 'ShowLayer', 
            'Camera', 'Transform', 'Pass', 'Label', 'Play', 'Stop',
            'Queue', 'Voice', 'Sound', 'Music', 'Pause', 'Comment',
            'Translate', 'TranslateBlock', 'EndTranslate', 'TranslateString',
            'TranslatePython', 'TranslateEarlyPython', 'TranslateSay'
        )
        
        def __init__(self):
            self._depth = 0
            self._max_depth = wells_config.MAX_RECURSION_DEPTH
            
        def analyze_block(self, block, depth=0):
            """Analisa recursivamente um bloco de instruções e extrai as consequências futuras"""
            if depth > self._max_depth:
                wells_log.warn(f"Profundidade máxima de recursão atingida em {depth}", "ANALISADOR")
                return []
                
            consequences = []
            
            if block is None:
                return consequences
                
            # Gerencia e padroniza os diferentes formatos de blocos do Ren'Py
            if isinstance(block, (list, tuple)):
                statements = block
            elif hasattr(block, 'children'):
                statements = block.children
            elif hasattr(block, '__iter__'):
                statements = list(block)
            else:
                return consequences
                
            for stmt in statements:
                try:
                    stmt_consequences = self._analyze_statement(stmt, depth)
                    consequences.extend(stmt_consequences)
                except self.CONTROL_EXCEPTIONS:
                    raise
                except Exception as e:
                    wells_log.error(f"Erro ao analisar instrução do roteiro: {e}", "ANALISADOR")
                    continue
                    
            return consequences
            
        def _analyze_statement(self, stmt, depth):
            """Analisa de forma individual uma instrução do roteiro do jogo"""
            consequences = []
            
            if stmt is None:
                return consequences
                
            stmt_class = stmt.__class__.__name__
            
            # Pula na hora se for apenas um elemento visual, áudio ou diálogo puro
            if stmt_class in self.SKIP_STATEMENTS:
                return consequences
                
            # Bloco de código Python nativo do jogo
            if stmt_class == 'Python':
                consequences.extend(self._analyze_python(stmt, depth))
                
            # Instrução de Salto de Roteiro (Jump)
            elif stmt_class == 'Jump':
                target = getattr(stmt, 'target', '?')
                consequences.append(WellsConsequence(
                    ConsequenceType.JUMP, target, '', f"→ {target}",
                    getattr(stmt, 'linenumber', 0)
                ))
                
            # Instrução de Chamada de Subrotina (Call)  
            elif stmt_class == 'Call':
                label = getattr(stmt, 'label', '?')
                consequences.append(WellsConsequence(
                    ConsequenceType.CALL, label, '', f"⇒ {label}",
                    getattr(stmt, 'linenumber', 0)
                ))
                
            # Instrução de Retorno (Return)
            elif stmt_class == 'Return':
                expr = getattr(stmt, 'expression', None)
                val = str(expr) if expr else 'fim'
                consequences.append(WellsConsequence(
                    ConsequenceType.RETURN, 'return', val, f"← {val}",
                    getattr(stmt, 'linenumber', 0)
                ))
                
            # Bloco Condicional (If / Elif / Else)
            elif stmt_class == 'If':
                consequences.extend(self._analyze_conditional(stmt, depth))
                
            # Laço de repetição (While)
            elif stmt_class == 'While':
                consequences.extend(self._analyze_while(stmt, depth))
                
            # Menu de escolhas aninhado (Submenu de escolhas interno)
            elif stmt_class == 'Menu':
                # Não faz recursão profunda em submenus de escolhas para evitar congelamentos
                pass
                
            # Declaração customizada criada pelo desenvolvedor (UserStatement)
            elif stmt_class == 'UserStatement':
                # Pode ser qualquer modificação customizada, tenta extrair informações genéricas
                pass
                
            else:
                # Tipo de instrução desconhecida, tenta inspecionar atributos básicos
                for attr in ['target', 'label', 'expression', 'name', 'value']:
                    if hasattr(stmt, attr):
                        value = getattr(stmt, attr)
                        if value and not str(value).startswith('_'):
                            consequences.append(WellsConsequence(
                                ConsequenceType.UNKNOWN,
                                f"{stmt_class}.{attr}", str(value)[:30], '',
                                getattr(stmt, 'linenumber', 0),
                                confidence=0.5
                            ))
                            break
                            
            return consequences

        def _analyze_python(self, stmt, depth):
            """Analisa uma instrução de código Python do jogo e extrai as consequências"""
            consequences = []
            source = None
            
            # Recupera o código-fonte bruto da instrução Python do Ren'Py
            if hasattr(stmt, 'code'):
                code_obj = stmt.code
                if hasattr(code_obj, 'source'):
                    source = code_obj.source
                elif hasattr(code_obj, 'py'):
                    source = code_obj.py
                    
            if not source:
                return consequences
                
            # Tenta processar o código primeiro usando o analisador de sintaxe AST do Python
            try:
                consequences.extend(self._parse_python_ast(source, depth))
            except:
                # Se falhar ou der erro de sintaxe, usa o processador alternativo por Expressões Regulares (Regex)
                consequences.extend(self._parse_python_regex(source))
                
            return consequences
            
        def _parse_python_ast(self, source, depth):
            """Analisa e desmonta o código-fonte Python utilizando a árvore estrutural AST"""
            consequences = []
            
            try:
                tree = _ast.parse(source)
                
                for node in _ast.walk(tree):
                    # Atribuição simples de variável comum: ex: x = valor
                    if isinstance(node, _ast.Assign):
                        for target in node.targets:
                            if isinstance(target, _ast.Name):
                                var_name = target.id
                                try:
                                    if hasattr(_ast, 'unparse'):
                                        value = _ast.unparse(node.value)
                                    elif isinstance(node.value, _ast.Constant):
                                        value = str(node.value.value)
                                    else:
                                        value = "?"
                                        
                                    # Detecta de forma inteligente o tipo de consequência com base no valor atribuído
                                    ctype = ConsequenceType.ASSIGN
                                    if value in ['True', 'False']:
                                        ctype = ConsequenceType.BOOLEAN
                                        
                                    consequences.append(WellsConsequence(
                                        ctype, var_name, value[:50]
                                    ))
                                except:
                                    consequences.append(WellsConsequence(
                                        ConsequenceType.ASSIGN, var_name, "?"
                                    ))
                    
                    # Atribuição incrementada ou decrementada: ex: x += 1 ou x -= 5
                    elif isinstance(node, _ast.AugAssign):
                        if isinstance(node.target, _ast.Name):
                            var_name = node.target.id
                            op = node.op.__class__.__name__
                            
                            try:
                                if hasattr(_ast, 'unparse'):
                                    value = _ast.unparse(node.value)
                                elif isinstance(node.value, _ast.Constant):
                                    value = str(node.value.value)
                                else:
                                    value = "?"
                            except:
                                value = "?"
                                
                            if op == 'Add': # Operação de Soma (Aumento)
                                consequences.append(WellsConsequence(
                                    ConsequenceType.INCREASE, var_name, value
                                ))
                            elif op == 'Sub': # Operação de Subtração (Diminuição)
                                consequences.append(WellsConsequence(
                                    ConsequenceType.DECREASE, var_name, value
                                ))
                    
                    # Estruturas condicionais internas do bloco Python (If interno)
                    elif isinstance(node, _ast.If):
                        try:
                            if hasattr(_ast, 'unparse'):
                                cond_text = _ast.unparse(node.test)
                            else:
                                cond_text = "condicao"
                                
                            if len(cond_text) > 30:
                                cond_text = cond_text[:27] + "..."
                                
                            consequences.append(WellsConsequence(
                                ConsequenceType.CONDITION, f"if {cond_text}", ""
                            ))
                        except:
                            pass
                    
                    # Chamadas de funções do Python nativo do jogo
                    elif isinstance(node, _ast.Call):
                        try:
                            if hasattr(_ast, 'unparse'):
                                call_text = _ast.unparse(node)
                            elif isinstance(node.func, _ast.Name):
                                call_text = node.func.id
                            elif isinstance(node.func, _ast.Attribute):
                                call_text = f"*.{node.func.attr}"
                            else:
                                call_text = "funcao"
                                
                            # Filtra e pula as funções visuais e internas do próprio motor Ren'Py
                            if not any(skip in call_text for skip in 
                                    ['renpy.pause', 'renpy.sound', 'renpy.music', 
                                    'renpy.scene', 'renpy.show', 'renpy.hide']):
                                consequences.append(WellsConsequence(
                                    ConsequenceType.FUNCTION, call_text[:40], ""
                                ))
                        except:
                            pass

            except SyntaxError:
                pass
            except Exception as e:
                wells_log.debug(f"Erro de análise na árvore AST: {e}", "ANALISADOR")
                
            return consequences
            
        def _parse_python_regex(self, source):
            """Processador alternativo utilizando expressões regulares (Regex) para varredura de código"""
            consequences = []
            
            lines = source.split('\n')
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                    
                # Atribuição incrementada (Soma: +=)
                if '+=' in line:
                    try:
                        var, val = line.split('+=', 1)
                        var = re.sub(r'\[.*?\]', '', var.strip())
                        consequences.append(WellsConsequence(
                            ConsequenceType.INCREASE, var, val.strip()[:20]
                        ))
                    except:
                        pass
                        
                # Atribuição decrementada (Subtração: -=)
                elif '-=' in line:
                    try:
                        var, val = line.split('-=', 1)
                        var = re.sub(r'\[.*?\]', '', var.strip())
                        consequences.append(WellsConsequence(
                            ConsequenceType.DECREASE, var, val.strip()[:20]
                        ))
                    except:
                        pass
                        
                # Atribuição regular simples (Garante ignorar operadores de comparação matemática e lógica)
                elif '=' in line and '==' not in line and '!=' not in line and '<=' not in line and '>=' not in line:
                    if not any(line.startswith(x) for x in ['if ', 'elif ', 'for ', 'while ', 'def ', 'class ']):
                        try:
                            var, val = line.split('=', 1)
                            var = re.sub(r'\[.*?\]', '', var.strip())
                            val = val.strip()
                            
                            if not var.startswith('_') and len(var) > 1:
                                ctype = ConsequenceType.ASSIGN
                                if val.lower() in ['true', 'false']:
                                    ctype = ConsequenceType.BOOLEAN
                                    
                                consequences.append(WellsConsequence(
                                    ctype, var, val[:20]
                                ))
                        except:
                            pass
                            
            return consequences
            
        def _analyze_conditional(self, stmt, depth):
            """Analisa e extrai as lógicas estruturais de um bloco Condicional (If)"""
            consequences = []
            
            if not hasattr(stmt, 'entries'):
                return consequences
                
            branch_info = []
            all_sub_consequences = []
            branch_consequences = {}  # Dicionário para armazenar as consequências separadas por ramificação
            
            num_entries = len(stmt.entries) if hasattr(stmt.entries, '__len__') else 0
            
            for idx, (condition, block) in enumerate(stmt.entries):
                is_last = (idx == num_entries - 1)
                
                if condition is not None:
                    cond_str = str(condition).strip()
                    if cond_str.startswith('store.'):
                        cond_str = cond_str[6:]
                    
                    is_else_branch = is_last and cond_str.lower() in ('true', '1')
                    
                    if is_else_branch:
                        branch_label = "else"
                        branch_key = "else"
                    else:
                        # Guarda a condição textual completa para servir de chave da ramificação
                        full_cond_str = cond_str
                        if len(cond_str) > 35:
                            cond_str = cond_str[:32] + "..."
                            
                        if idx == 0:
                            branch_label = f"if {cond_str}"
                            branch_key = f"if {full_cond_str}"
                        else:
                            branch_label = f"elif {cond_str}"
                            branch_key = f"elif {full_cond_str}"
                else:
                    branch_label = "else"
                    branch_key = "else"
                    
                branch_info.append(branch_label)
                    
                if block and depth < self._max_depth:
                    sub_cons = self.analyze_block(block, depth + 1)
                    all_sub_consequences.extend(sub_cons)
                    # Armazena as consequências encontradas nesta ramificação específica
                    branch_consequences[branch_key] = sub_cons
                else:
                    branch_consequences[branch_key] = []
                    
            # Cria a consequência estrutural do bloco condicional para exibição
            if branch_info:
                if len(branch_info) == 1:
                    cond_text = branch_info[0]
                elif len(branch_info) == 2 and branch_info[1] == "else":
                    cond_text = f"{branch_info[0]}/else"
                else:
                    cond_text = f"{branch_info[0]} (+{len(branch_info)-1})"
                    
                consequences.append(WellsConsequence(
                    ConsequenceType.CONDITION, cond_text, str(len(all_sub_consequences)),
                    source_line=getattr(stmt, 'linenumber', 0),
                    sub_consequences=all_sub_consequences,  # Lista linear para manter retrocompatibilidade
                    branch_consequences=branch_consequences  # Lista organizada estruturalmente por ramificação
                ))
                
            # Adiciona também as subconsequências de alta relevância diretamente na lista principal do botão
            important_types = [ConsequenceType.INCREASE, ConsequenceType.DECREASE,
                            ConsequenceType.JUMP, ConsequenceType.CALL]
            for sub in all_sub_consequences:
                if sub.type in important_types:
                    consequences.append(sub)
                    
            return consequences

        def _analyze_while(self, stmt, depth):
            """Analisa e extrai as lógicas estruturais de um laço de repetição (While)"""
            consequences = []
            
            if hasattr(stmt, 'condition'):
                cond_str = str(stmt.condition)[:30]
                consequences.append(WellsConsequence(
                    ConsequenceType.CONDITION, f"while {cond_str}", ""
                ))
                
            if hasattr(stmt, 'block') and depth < self._max_depth:
                consequences.extend(self.analyze_block(stmt.block, depth + 1))
                
            return consequences
    
    # Instância global do analisador estrutural utilizando o seu nick
    wells_analyzer = WellsAnalyzer()

    ##################################################################
    #                LOCALIZADOR DE MENUS DO WELLS                   #
    ##################################################################
    
    class WellsMenuFinder:
        """Detecção avançada de menus de escolha utilizando múltiplas estratégias"""
        
        def __init__(self):
            self._strategy_scores = {}
            self._seen_menus_by_label = {}    # dicionário formato: label -> [linha_menu, linha_menu, ...]
            self._last_label = None
            self._menu_index_in_label = 0
            self._global_menu_history = []    # Lista global contendo as linhas de menus já encontradas
            self._global_menu_index = 0
            
        def reset_sequence(self, label=None):
            """Redefine o rastreamento de sequências (útil na mudança de label ou reinício do jogo)"""
            if label:
                self._seen_menus_by_label[label] = []
            else:
                self._seen_menus_by_label.clear()
            self._menu_index_in_label = 0
            self._global_menu_history = []
            self._global_menu_index = 0
            
        def find_menu_node(self, items):
            """Localiza o nó AST do menu correto para os itens de escolha fornecidos"""
            wells_log.debug(f"Localizando menu com {len(items)} opções disponíveis", "LOCALIZADOR_MENU")
            
            context = self._get_execution_context()
            if not context:
                wells_log.warn("Nenhum contexto de execução disponível no momento", "LOCALIZADOR_MENU")
                return None, None
            
            current_label = context.get('label')
            if current_label != self._last_label:
                self._last_label = current_label
                self._menu_index_in_label = 0
                wells_log.debug(f"A Label atual do jogo mudou para: {current_label}", "LOCALIZADOR_MENU")
                
            cache_key = self._create_cache_key(items, context)
            
            cached = wells_menu_cache.get(cache_key)
            if cached:
                wells_log.debug(f"Menu de escolhas encontrado no cache (índice {self._menu_index_in_label})", "LOCALIZADOR_MENU")
                self._menu_index_in_label += 1
                return cached
                
            # Estratégia 1: Busca direta na pilha de execução de código ativa
            result = self._find_via_execution_stack(items, context)
            if result[0]:
                self._record_seen_menu(result[0], context)
                wells_menu_cache.set(cache_key, result)
                return result
                
            # Estratégia 2: Busca por mapeamento sequencial (para escolhas duplicadas como Sim/Não)
            result = self._find_via_sequence(items, context)
            if result[0]:
                self._record_seen_menu(result[0], context)
                wells_menu_cache.set(cache_key, result)
                return result
                
            # Estratégia 3: Proximidade do arquivo físico e da linha de código
            result = self._find_via_proximity(items, context)
            if result[0]:
                self._record_seen_menu(result[0], context)
                wells_menu_cache.set(cache_key, result)
                return result
                
            # Estratégia 4: Comparação textual entre todos os menus registrados do jogo
            result = self._find_via_text_match(items, context)
            if result[0]:
                self._record_seen_menu(result[0], context)
                wells_menu_cache.set(cache_key, result)
                return result
                
            wells_log.warn("Não foi possível encontrar nenhum nó de menu correspondente", "LOCALIZADOR_MENU")
            # Incrementa o índice mesmo em falhas para manter a consistência da sequência de leitura
            self._menu_index_in_label += 1
            return None, None
        
        def _record_seen_menu(self, menu_node, context):
            """Registra internamente que este menu específico de escolhas já foi lido"""
            label = context.get('label', '__global__')
            if label not in self._seen_menus_by_label:
                self._seen_menus_by_label[label] = []
            if hasattr(menu_node, 'linenumber'):
                self._seen_menus_by_label[label].append(menu_node.linenumber)
                # Adiciona o registro também ao histórico sequencial global
                self._global_menu_history.append(menu_node.linenumber)
            self._menu_index_in_label += 1
            self._global_menu_index += 1
            
        def _get_caption_signature(self, items):
            """Gera uma assinatura de texto padronizada com base nos botões de escolha"""
            captions = []
            for item in items:
                if hasattr(item, 'caption'):
                    text = str(item.caption)
                elif isinstance(item, (list, tuple)) and len(item) > 0:
                    text = str(item[0])
                else:
                    text = str(item)
                # Limpa tags visuais e normaliza em minúsculas
                clean = re.sub(r'\{[^}]*\}', '', text).strip().lower()
                captions.append(clean)
            return "|".join(sorted(captions))  # Ordena para manter consistência absoluta
            
        def _find_via_sequence(self, items, context):
            """Busca um menu usando a ordem de sequência global para diferenciar opções duplicadas"""
            try:
                script = renpy.game.script
                
                # Gera a assinatura dos botões de escolhas atuais
                caption_sig = self._get_caption_signature(items)
                
                # Procura por TODOS os menus do jogo atual que possuam botões idênticos
                matching_menus = []
                
                for node_name, node in script.namemap.items():
                    if not isinstance(node, renpy.ast.Menu):
                        continue
                    if not hasattr(node, 'items') or not hasattr(node, 'linenumber'):
                        continue
                    
                    # Valida se os textos dos botões combinam perfeitamente
                    if self._items_match(node.items, items):
                        matching_menus.append(node)
                
                if not matching_menus:
                    return None, None

                # Ordena por nome de arquivo e depois pelo número da linha para manter um padrão consistente
                matching_menus.sort(key=lambda n: (n.filename or '', n.linenumber))
                
                wells_log.debug(f"Encontrados {len(matching_menus)} menus correspondentes para '{caption_sig[:30]}...'", "LOCALIZADOR_MENU")
                
                # Se houver apenas uma correspondência exata, retorna ela imediatamente
                if len(matching_menus) == 1:
                    return matching_menus[0], {'strategy': 'sequence_single', 'offset': 0}
                
                # Múltiplas correspondências - usa o histórico sequencial global para achar o menu correto
                # Procura por menus que ainda não foram exibidos ou retornados (baseado no número da linha)
                seen_lines = set(self._global_menu_history)
                
                for menu in matching_menus:
                    if menu.linenumber not in seen_lines:
                        wells_log.debug(f"Correspondência sequencial: linha {menu.linenumber} (inédito, índice global {self._global_menu_index})", "LOCALIZADOR_MENU")
                        return menu, {'strategy': 'sequence_global', 'offset': 0}
                
                # Se todos já foram vistos, usa o resto da divisão (módulo) do índice global para fazer um ciclo limpo
                idx = self._global_menu_index % len(matching_menus)
                menu = matching_menus[idx]
                wells_log.debug(f"Correspondência sequencial: linha {menu.linenumber} (pelo índice global {self._global_menu_index} -> {idx})", "LOCALIZADOR_MENU")
                return menu, {'strategy': 'sequence_index', 'offset': 0}
                
            except Exception as e:
                wells_log.error(f"Erro na busca sequencial de menus: {e}", "LOCALIZADOR_MENU")
                return None, None
            
        def _get_execution_context(self):
            """Recupera e monta o contexto atual de execução do jogo de forma segura"""
            try:
                ctx = renpy.game.context()
                if not ctx:
                    return None
                
                context = {
                    'filename': None,
                    'linenumber': 0,
                    'label': None,
                    'call_stack': [],
                    'menu_node': None
                }
                
                script = renpy.game.script
                
                # Função auxiliar para inspecionar um nó pelo nome e extrair sua localização física
                def get_node_location(node_name):
                    """Retorna uma tupla (nome_arquivo, numero_linha) localizando o nó no mapa de scripts"""
                    try:
                        if node_name is None:
                            return None, 0
                        # Localiza o nó específico na tabela de nomes (namemap) do jogo
                        node = script.lookup(node_name)
                        if node and hasattr(node, 'filename') and hasattr(node, 'linenumber'):
                            return node.filename, node.linenumber
                    except Exception:
                        pass
                    return None, 0
                
                # Método 1 de varredura: Inspeciona o nó ativo atual da pilha
                if hasattr(ctx, 'current') and ctx.current:
                    node_name = ctx.current
                    try:
                        node = script.lookup(node_name)
                        if node:
                            if hasattr(node, 'filename') and hasattr(node, 'linenumber'):
                                context['filename'] = node.filename
                                context['linenumber'] = node.linenumber
                            if isinstance(node, renpy.ast.Menu):
                                context['menu_node'] = node
                    except Exception as e:
                        wells_log.debug(f"Não foi possível inspecionar o nó ativo atual: {e}", "LOCALIZADOR_MENU")
                
                # Método 2 de varredura: Inspeciona a pilha de localização de chamadas (call stack)
                if not context['filename'] and hasattr(ctx, 'call_location_stack'):
                    stack = ctx.call_location_stack
                    if isinstance(stack, (list, tuple)) and stack:
                        for node_name in reversed(list(stack)):
                            filename, linenumber = get_node_location(node_name)
                            if filename:
                                context['filename'] = filename
                                context['linenumber'] = linenumber
                                break
                
                # Método 3 de varredura: Inspeciona a pilha de retornos pendentes (return stack)
                if not context['filename'] and hasattr(ctx, 'return_stack'):
                    stack = ctx.return_stack
                    if isinstance(stack, (list, tuple)) and stack:
                        for node_name in reversed(list(stack)):
                            filename, linenumber = get_node_location(node_name)
                            if filename:
                                context['filename'] = filename
                                context['linenumber'] = linenumber
                                break
                
                # Trava de estabilidade crucial: Converte arquivos lidos como compilados (.rpyc) para o código cru (.rpy)
                if context['filename']:
                    context['filename'] = context['filename'].replace('.rpyc', '.rpy')
                
                # Descobre qual é a Label ativa correspondente a este arquivo e linha de código
                if context['filename'] and hasattr(renpy.game, 'script'):
                    script = renpy.game.script
                    best_label = None
                    best_line = -1
                    
                    for node_name, node in script.namemap.items():
                        if (isinstance(node, renpy.ast.Label) and
                            hasattr(node, 'filename') and hasattr(node, 'linenumber') and
                            node.filename == context['filename'] and
                            node.linenumber <= context['linenumber'] and
                            node.linenumber > best_line):
                            best_label = node.name
                            best_line = node.linenumber
                            
                    context['label'] = best_label
                    
                # Captura o histórico recente da pilha de chamadas para controle de subrotinas
                if hasattr(ctx, 'return_stack'):
                    stack = ctx.return_stack
                    if isinstance(stack, (list, tuple)):
                        context['call_stack'] = list(stack[-5:])
                    
                return context

            except Exception as e:
                wells_log.error(f"Erro ao obter contexto de execução: {e}", "LOCALIZADOR_MENU")
                return None
                
        def _create_cache_key(self, items, context):
            """Cria uma chave de cache única incluindo o índice sequencial para evitar menus duplicados"""
            item_texts = []
            for item in items:
                if hasattr(item, 'caption'):
                    item_texts.append(str(item.caption))
                elif isinstance(item, (list, tuple)) and len(item) > 0:
                    item_texts.append(str(item[0]))
                else:
                    item_texts.append(str(item))
            
            return (
                context.get('filename', ''),
                self._global_menu_index,
                tuple(item_texts)
            )
            
        def _find_via_execution_stack(self, items, context):
            """Busca um nó de menu utilizando a pilha ativa de execução de código do jogo"""
            try:
                # Se o coletor de contexto já mapeou o nó do menu diretamente, usa ele na hora
                if context.get('menu_node'):
                    return context['menu_node'], {'strategy': 'context_node', 'offset': 0}
                
                ctx = renpy.game.context()
                script = renpy.game.script
                
                if hasattr(ctx, 'current') and ctx.current:
                    try:
                        node = script.lookup(ctx.current)
                        if isinstance(node, renpy.ast.Menu):
                            return node, {'strategy': 'execution_stack', 'offset': 0}
                    except Exception:
                        pass
                
                # Varre a tabela global em busca de blocos que coincidam com as opções da tela
                if hasattr(renpy.game, 'script'):
                    for node_name, node in script.namemap.items():
                        if isinstance(node, renpy.ast.Menu) and hasattr(node, 'items'):
                            if self._items_match(node.items, items):
                                return node, {'strategy': 'item_match', 'offset': 0}
                        
                return None, None
            except:
                return None, None
        
        def _items_match(self, ast_items, runtime_items):
            """Verifica de forma flexível se os botões extraídos da AST batem com os botões ativos em tela"""
            # Extrai os textos das opções em tempo de execução
            runtime_captions = []
            for item in runtime_items:
                if hasattr(item, 'caption'):
                    caption = str(item.caption)
                elif isinstance(item, (list, tuple)) and len(item) > 0:
                    caption = str(item[0])
                else:
                    caption = str(item)
                clean = re.sub(r'\{[^}]*\}', '', caption).strip()
                runtime_captions.append(clean)
            
            # Extrai os textos originais salvos na estrutura de código AST
            ast_captions = []
            for item in ast_items:
                if item and len(item) >= 1:
                    caption = str(item[0]) if item[0] else ""
                    clean = re.sub(r'\{[^}]*\}', '', caption).strip()
                    ast_captions.append(clean)
            
            # Faz uma contagem de quantas opções batem perfeitamente
            matches = 0
            for rc in runtime_captions:
                if rc in ast_captions:
                    matches += 1
            
            # Considera válido se pelo menos 80% das opções forem encontradas (segurança para textos dinâmicos)
            return matches >= len(runtime_captions) * 0.8
                
        def _find_via_proximity(self, items, context):
            """Busca um menu analisando a proximidade das linhas físicas de código nos scripts (.rpy)"""
            try:
                script = renpy.game.script
                filename = context['filename']
                linenumber = context['linenumber']
                
                filename_base = filename.replace('.rpyc', '.rpy') if filename else ''
                
                candidates = []
                
                for node_name, node in script.namemap.items():
                    if not isinstance(node, renpy.ast.Menu):
                        continue
                    if not hasattr(node, 'filename') or not hasattr(node, 'items'):
                        continue
                        
                    node_file = node.filename.replace('.rpyc', '.rpy') if node.filename else ''
                    
                    if node_file != filename_base and not node_file.endswith(filename_base.split('/')[-1]):
                        continue
                        
                    # Executa o cálculo matemático de pontuação por proximidade
                    score, info = self._calculate_match_score(node, items, linenumber)
                    if score > 0:
                        candidates.append((node, score, info))
                        
                if not candidates:
                    return None, None
                    
                # Ordena os candidatos para deixar o de maior pontuação no topo
                candidates.sort(key=lambda x: -x[1])
                
                best_node, best_score, best_info = candidates[0]
                wells_log.debug(f"Menu encontrado na linha {best_node.linenumber} por aproximação (Pontuação: {best_score})", "LOCALIZADOR_MENU")
                
                return best_node, best_info
                
            except Exception as e:
                wells_log.error(f"Erro na busca de menus por proximidade: {e}", "LOCALIZADOR_MENU")
                return None, None

        def _find_via_text_match(self, items, context):
            """Busca um menu usando correspondência textual direta entre os botões (último recurso)"""
            try:
                script = renpy.game.script
                item_texts = []
                for item in items:
                    if hasattr(item, 'caption'):
                        text = str(item.caption)
                    elif isinstance(item, (list, tuple)) and len(item) > 0:
                        text = str(item[0])
                    else:
                        text = str(item)
                    item_texts.append(re.sub(r'\{[^}]*\}', '', text).strip())
                
                best_match = None
                best_score = 0
                best_info = None
                
                for node_name, node in script.namemap.items():
                    if not isinstance(node, renpy.ast.Menu) or not hasattr(node, 'items'):
                        continue
                        
                    score, info = self._text_match_score(node, item_texts)
                    if score > best_score:
                        best_score = score
                        best_match = node
                        best_info = info
                        
                if best_match and best_score >= len(items) * 8:  # Requer pelo menos 80% de correspondência
                    return best_match, best_info
                    
                return None, None
                
            except Exception as e:
                wells_log.error(f"Erro na busca por correspondência de texto: {e}", "LOCALIZADOR_MENU")
                return None, None
                
        def _calculate_match_score(self, node, items, target_line):
            """Calcula a pontuação de proximidade de um menu - prioriza o texto sobre a linha física"""
            score = 0
            info = {'strategy': 'proximity', 'offset': 0}
            
            node_items = node.items
            distance = abs(node.linenumber - target_line)
            
            text_matches = self._count_text_matches(node_items, items)
            text_match_ratio = text_matches / max(len(items), 1)
            
            # A correspondência de texto é a pontuação principal (até 200 pontos)
            if text_match_ratio >= 1.0:
                score += 200  # Combinação Perfeita
                info['strategy'] = 'text_match'
            elif text_match_ratio >= 0.8:
                score += 150
                info['strategy'] = 'text_match'
            elif text_match_ratio >= 0.5:
                score += 100
            else:
                score += int(text_match_ratio * 50)
            
            # A distância física de linhas é secundária (até 50 pontos)
            # Só faz diferença real se a correspondência de texto for inconclusiva
            if distance <= 5:
                score += 50
            elif distance <= 20:
                score += 40
            elif distance <= 50:
                score += 30
            elif distance <= 100:
                score += 20
            elif distance <= 500:
                score += 10
            else:
                score += 5
                
            # Pontuação por quantidade de botões de escolha (até 30 pontos)
            if len(node_items) == len(items):
                score += 30
                if info['strategy'] == 'proximity':
                    info['strategy'] = 'exact'
            elif len(node_items) == len(items) + 1:
                score += 15
                if info['strategy'] == 'proximity':
                    info['strategy'] = 'skip_first'
                    info['offset'] = 1
            elif len(node_items) + 1 == len(items):
                score += 10
                if info['strategy'] == 'proximity':
                    info['strategy'] = 'partial'
            
            return score, info
        
        def _count_text_matches(self, node_items, runtime_items):
            """Conta quantas opções em execução coincidem com os nós do script através do texto"""
            # Extrai os textos das opções gravadas no script do nó
            node_texts = set()
            for item in node_items:
                if item and len(item) > 0:
                    text = str(item[0]) if item[0] else ""
                    clean = re.sub(r'\{[^}]*\}', '', text).strip().lower()
                    if clean:
                        node_texts.add(clean)
            
            # Conta as combinações encontradas
            matches = 0
            for item in runtime_items:
                if hasattr(item, 'caption'):
                    text = str(item.caption)
                elif isinstance(item, (list, tuple)) and len(item) > 0:
                    text = str(item[0])
                else:
                    text = str(item)
                clean = re.sub(r'\{[^}]*\}', '', text).strip().lower()
                if clean in node_texts:
                    matches += 1
            
            return matches

        def _text_match_score(self, node, item_texts):
            """Calcula a pontuação de correspondência de texto entre as opções do nó e da tela"""
            score = 0
            info = {'strategy': 'text_match', 'offset': 0}
            
            node_texts = []
            for item in node.items:
                if item and len(item) > 0:
                    text = str(item[0]) if item[0] else ""
                    clean = re.sub(r'\{[^}]*\}', '', text).strip()
                    node_texts.append(clean)
                    
            for offset in range(min(2, len(node_texts))):
                aligned_score = 0
                for i, item_text in enumerate(item_texts):
                    node_idx = i + offset
                    if node_idx < len(node_texts):
                        if node_texts[node_idx] == item_text:
                            aligned_score += 10
                        elif node_texts[node_idx].lower() == item_text.lower():
                            aligned_score += 8
                        elif item_text in node_texts[node_idx] or node_texts[node_idx] in item_text:
                            aligned_score += 4
                            
                if aligned_score > score:
                    score = aligned_score
                    info['offset'] = offset
                    
            return score, info
    
    # Instância global do localizador de menus utilizando o seu nick
    wells_menu_finder = WellsMenuFinder()

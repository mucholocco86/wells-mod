####################################################################
####            Sistema do Menu Universal do Wells v2.0          ####
####                       Modificado por Wells                 ####
####            Utilitários, Compatibilidade e Extensões        ####
####################################################################

init -996 python:
    ##################################################################
    #               CAMADA DE COMPATIBILIDADE WELLS                  #
    ##################################################################
    
    class WellsCompatibility:
        """Fornece compatibilidade com as configurações persistentes originais do URW 1.x"""
        
        @staticmethod
        def migrate_settings():
            """Migra as configurações do antigo URW 1.x de forma segura"""
            # Trava de segurança contra congelamentos no SHIFT+R e rollbacks
            if renpy.game.after_rollback:
                return
            
            # Verifica se as configurações antigas existem e migra para o novo sistema do Wells
            if hasattr(persistent, 'universal_walkthrough_enabled'):
                persistent.wells_enabled = persistent.universal_walkthrough_enabled
                wells_log.info("Migrado com sucesso: universal_walkthrough_enabled", "COMPATIBILIDADE")
                
            if hasattr(persistent, 'universal_wt_text_size'):
                persistent.wells_text_size = persistent.universal_wt_text_size
                wells_log.info("Migrado com sucesso: universal_wt_text_size", "COMPATIBILIDADE")
                
            if hasattr(persistent, 'universal_wt_max_consequences'):
                persistent.wells_max_consequences = persistent.universal_wt_max_consequences
                wells_log.info("Migrado com sucesso: universal_wt_max_consequences", "COMPATIBILIDADE")
                
            if hasattr(persistent, 'universal_wt_show_all_available'):
                persistent.wells_show_all = persistent.universal_wt_show_all_available
                wells_log.info("Migrado com sucesso: universal_wt_show_all_available", "COMPATIBILIDADE")
                
            # Migração dos filtros de exibição
            if hasattr(persistent, 'universal_wt_filters'):
                old_filters = persistent.universal_wt_filters
                
                if old_filters is None:
                    old_filters = {}
                
                # Mapeia os nomes dos filtros antigos para a nova estrutura do Wells
                filter_map = {
                    'conditions': 'conditions',
                    'jumps': 'flow',
                    'calls': 'flow',
                    'returns': 'flow',
                    'increases': 'variables',
                    'decreases': 'variables',
                    'assignments': 'variables',
                    'booleans': 'flags',
                    'functions': 'functions',
                    'code': 'variables',
                    'unknown': 'unknown'
                }
                
                for old_key, new_key in filter_map.items():
                    if old_key in old_filters:
                        # Aplica uma operação lógica OU com o valor existente
                        current = persistent.wells_filters.get(new_key, True)
                        persistent.wells_filters[new_key] = current or old_filters[old_key]
                        
                wells_log.info("Migrado com sucesso: configurações de filtros", "COMPATIBILIDADE")
                
            # Migração dos filtros de nomes de variáveis
            if hasattr(persistent, 'universal_wt_name_filters'):
                old_name_filters = persistent.universal_wt_name_filters
                
                if old_name_filters is None:
                    old_name_filters = {}
                
                direct_map = {
                    'hide_underscore': 'hide_underscore',
                    'hide_renpy': 'hide_renpy',
                    'hide_config': 'hide_config',
                    'hide_store': 'hide_store'
                }
                
                for old_key, new_key in direct_map.items():
                    if old_key in old_name_filters:
                        persistent.wells_name_filters[new_key] = old_name_filters[old_key]
                        
                # Gerencia os filtros customizados por prefixo
                if 'custom_prefix' in old_name_filters and old_name_filters['custom_prefix']:
                    prefixes = [p.strip() for p in old_name_filters['custom_prefix'].split(';') if p.strip()]
                    persistent.wells_name_filters['custom_hide'] = prefixes
                    
                wells_log.info("Migrado com sucesso: filtros de nomes de variáveis", "COMPATIBILIDADE")
    
    # Executa a migração automática ao iniciar o script
    WellsCompatibility.migrate_settings()

    ##################################################################
    #               RASTRADOR DE VARIÁVEIS DO WELLS                  #
    ##################################################################
    
    class WellsVariableTracker:
        """Rastreia e monitora as mudanças de variáveis durante o jogo"""
        
        def __init__(self):
            self._tracked_vars = set()       # Conjunto de variáveis monitoradas
            self._history = []               # Histórico de alterações realizadas
            self._max_history = 1000         # Limite máximo de registros no histórico
            self._snapshot = {}              # Foto instantânea do estado das variáveis
            
        def track(self, var_name):
            """Adiciona uma variável para a lista de monitoramento"""
            self._tracked_vars.add(var_name)
            
        def untrack(self, var_name):
            """Remove uma variável da lista de monitoramento"""
            self._tracked_vars.discard(var_name)
            
        def take_snapshot(self):
            """Tira uma foto instantânea (captura o estado atual) das variáveis monitoradas"""
            store = renpy.store
            self._snapshot = {}
            
            for var in self._tracked_vars:
                if hasattr(store, var):
                    self._snapshot[var] = getattr(store, var)
                    
        def get_changes(self):
            """Obtém as alterações feitas nas variáveis desde a última foto tirada"""
            changes = []
            store = renpy.store
            
            for var in self._tracked_vars:
                if hasattr(store, var):
                    current = getattr(store, var)
                    old = self._snapshot.get(var)
                    
                    if old != current:
                        changes.append({
                            'variable': var,
                            'old': old,
                            'new': current,
                            'timestamp': _time.time()
                        })
                        
            return changes
            
        def record_change(self, var_name, old_value, new_value):
            """Grava e registra uma alteração de variável no histórico"""
            self._history.append({
                'variable': var_name,
                'old': old_value,
                'new': new_value,
                'timestamp': _time.time()
            })
            
            # Corta o histórico pela metade se ele passar do limite máximo definido
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history//2:]
                
        def get_history(self, var_name=None, count=50):
            """Recupera o histórico de alterações gravadas"""
            if var_name:
                return [h for h in self._history if h['variable'] == var_name][-count:]
            return self._history[-count:]
            
        def clear_history(self):
            """Limpa completamente o histórico de alterações de variáveis"""
            self._history.clear()
    
    # Instancia o rastreador global utilizando o seu nick
    wells_var_tracker = WellsVariableTracker()

    ##################################################################
    #                 HISTÓRICO DE ESCOLHAS DO WELLS                 #
    ##################################################################
    
    class WellsChoiceHistory:
        """Rastreia as escolhas do jogador para fins de estatísticas e análise"""
        
        def __init__(self):
            self._session_choices = []       # Armazena as escolhas feitas na sessão atual de jogo
            
        def record_choice(self, menu_label, choice_text, choice_index, consequences):
            """Grava e registra uma escolha feita pelo jogador"""
            entry = {
                'menu_label': menu_label,
                'choice_text': choice_text[:100],  # Corta textos muito longos para economizar memória
                'choice_index': choice_index,
                'consequence_count': len(consequences),
                'timestamp': _time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Adiciona ao histórico da sessão atual
            self._session_choices.append(entry)
            
            # Garante que a lista persistente global exista
            if not persistent.wells_choice_history:
                persistent.wells_choice_history = []
                
            # Salva de forma permanente no histórico do jogador
            persistent.wells_choice_history.append(entry)
            
            # Se o histórico persistente passar do limite configurado, remove os registros mais antigos
            max_history = persistent.wells_max_history
            if len(persistent.wells_choice_history) > max_history:
                persistent.wells_choice_history = persistent.wells_choice_history[-max_history:]
                
        def get_session_choices(self):
            """Retorna a lista de escolhas feitas na sessão de jogo atual"""
            return self._session_choices
            
        def get_all_choices(self):
            """Retorna a lista completa de todas as escolhas salvas no histórico permanente"""
            return persistent.wells_choice_history or []
            
        def get_choice_stats(self):
            """Gera e retorna estatísticas calculadas sobre as escolhas do jogador"""
            choices = self.get_all_choices()
            
            if not choices:
                return {'total': 0}
                
            return {
                'total': len(choices),
                'session': len(self._session_choices),
                'avg_consequences': sum(c['consequence_count'] for c in choices) / len(choices)
            }
            
        def clear_history(self):
            """Limpa completamente o histórico da sessão e o histórico persistente do computador"""
            self._session_choices.clear()
            persistent.wells_choice_history = []
    
    # Instancia o gerenciador de histórico global utilizando o seu nick
    wells_choice_history = WellsChoiceHistory()

    ##################################################################
    #                PROTEÇÃO DE SPOILER DO WELLS                    #
    ##################################################################
    
    class WellsSpoilerGuard:
        """Protege o jogador contra spoilers nas dicas do guia de escolhas (walkthrough)"""
        
        # Palavras-chave que podem indicar a presença de spoilers importantes na história
        SPOILER_KEYWORDS = frozenset([
            'death', 'dies', 'dead', 'kill', 'murder', 'ending', 'finale',
            'secret', 'hidden', 'reveal', 'twist', 'surprise', 'betray',
            'pregnant', 'wedding', 'marriage', 'divorce'
        ])
        
        def __init__(self):
            self._enabled = False            # Define se a proteção está ativada por padrão
            
        def enable(self):
            """Ativa a proteção contra spoilers"""
            self._enabled = True
            
        def disable(self):
            """Desativa a proteção contra spoilers"""
            self._enabled = False
            
        def is_enabled(self):
            """Verifica se a proteção contra spoilers está ligada ou desligada"""
            return self._enabled
            
        def filter_consequence(self, consequence):
            """Verifica se uma consequência específica de variável deve ser escondida devido a spoilers"""
            if not self._enabled:
                return False  # Se a proteção estiver desligada, nada é filtrado
                
            var_lower = str(consequence.variable).lower()
            val_lower = str(consequence.value).lower()
            
            # Varre as palavras-chave para detectar possíveis spoilers nas variáveis ou valores
            for keyword in self.SPOILER_KEYWORDS:
                if keyword in var_lower or keyword in val_lower:
                    return True  # Filtra e esconde esta consequência específica
                    
            return False
            
        def censor_text(self, text):
            """Censura textos de dicas que contenham spoilers em potencial"""
            if not self._enabled:
                return text
                
            text_lower = text.lower()
            
            # Verifica se alguma palavra-chave de spoiler está presente no texto da dica
            for keyword in self.SPOILER_KEYWORDS:
                if keyword in text_lower:
                    return "[Spoiler Ocultado]" # Substitui o texto original para proteger a história
                    
            return text
    
    # Instancia a proteção de spoilers global utilizando o seu nick
    wells_spoiler_guard = WellsSpoilerGuard()

    ##################################################################
    #                ANALISADOR DE MELHOR ESCOLHA DO WELLS           #
    ##################################################################
    
    class WellsBestChoiceAnalyzer:
        """Analisa as opções para sugerir a 'melhor' escolha (recurso opcional)"""
        
        # Padrões e termos comuns para identificar variáveis de status positivas
        POSITIVE_PATTERNS = [
            'love', 'trust', 'affection', 'relationship', 'friendship',
            'respect', 'loyalty', 'points', 'money', 'health', 'reputation'
        ]
        
        def __init__(self):
            self._enabled = False            # Define se o realce está ativado por padrão
            
        def enable(self):
            """Ativa a análise de melhor escolha"""
            self._enabled = True
            
        def disable(self):
            """Desativa a análise de melhor escolha"""
            self._enabled = False
            
        def analyze_choices(self, menu_node, match_info):
            """Analisa todas as opções de escolha e retorna o índice da melhor delas"""
            if not self._enabled:
                return None
                
            scores = []                      # Lista para armazenar as pontuações de cada botão
            
            for i in range(len(menu_node.items)):
                try:
                    # Comunica com o processador do Wells para prever as consequências da escolha
                    consequences = wells_processor.process_choice(menu_node, i, match_info)
                    score = self._score_consequences(consequences)
                    scores.append((i, score))
                except:
                    scores.append((i, 0))
                    
            if not scores:
                return None
                
            # Retorna o índice do botão que recebeu a maior pontuação acumulada
            best = max(scores, key=lambda x: x[1])
            return best[0] if best[1] > 0 else None
            
        def _score_consequences(self, consequences):
            """Calcula uma pontuação com base no impacto das consequências de uma escolha"""
            score = 0
            
            for cons in consequences:
                var_lower = str(cons.variable).lower()
                
                # Verifica se a variável que vai mudar é uma variável de ganho positivo
                is_positive = any(p in var_lower for p in self.POSITIVE_PATTERNS)
                
                # Aplica regras de pontuação com base no tipo de alteração (Aumento, Diminuição ou Booleano)
                if cons.type == ConsequenceType.INCREASE:
                    score += 10 if is_positive else 5
                elif cons.type == ConsequenceType.DECREASE:
                    score -= 10 if is_positive else 5
                elif cons.type == ConsequenceType.BOOLEAN:
                    if str(cons.value).lower() == 'true' and is_positive:
                        score += 5
                        
            return score
    
    # Instancia o analisador de melhores escolhas global utilizando o seu nick
    wells_best_analyzer = WellsBestChoiceAnalyzer()

    ##################################################################
    #                GERENCIADOR DE DADOS DO WELLS                   #
    ##################################################################
    
    class WellsDataManager:
        """Exporta, importa e restaura as configurações do sistema do Wells"""
        
        @staticmethod
        def export_settings():
            """Exporta todas as configurações atuais como um dicionário"""
            return {
                'version': wells_config.VERSION,
                'enabled': persistent.wells_enabled,
                'text_size': persistent.wells_text_size,
                'max_consequences': persistent.wells_max_consequences,
                'show_all': persistent.wells_show_all,
                'theme': persistent.wells_theme,
                'filters': dict(persistent.wells_filters),
                'name_filters': dict(persistent.wells_name_filters)
            }
            
        @staticmethod
        def import_settings(data):
            """Importa e aplica as configurações a partir de um dicionário"""
            if 'enabled' in data:
                persistent.wells_enabled = data['enabled']
            if 'text_size' in data:
                persistent.wells_text_size = data['text_size']
            if 'max_consequences' in data:
                persistent.wells_max_consequences = data['max_consequences']
            if 'show_all' in data:
                persistent.wells_show_all = data['show_all']
            if 'theme' in data:
                persistent.wells_theme = data['theme']
            if 'filters' in data:
                persistent.wells_filters.update(data['filters'])
            if 'name_filters' in data:
                persistent.wells_name_filters.update(data['name_filters'])
                
            wells_log.info("Configurações importadas com sucesso", "DADOS")
            
        @staticmethod
        def reset_all():
            """Restaura todas as configurações para os valores padrões de fábrica"""
            persistent.wells_enabled = True
            persistent.wells_text_size = 25
            persistent.wells_max_consequences = 3
            persistent.wells_show_all = True
            persistent.wells_theme = "modern"
            persistent.wells_spoiler_mode = False
            persistent.wells_highlight_best = True
            
            # Filtros padrões para exibição de dados
            persistent.wells_filters = {
                'variables': True,
                'conditions': True,
                'flow': True,
                'functions': True,
                'flags': True,
                'relationships': True,
                'stats': True,
                'unknown': False
            }
            
            # Filtros padrões para ocultação de nomes internos do Ren'Py
            persistent.wells_name_filters = {
                'hide_underscore': True,
                'hide_renpy': True,
                'hide_config': False,
                'hide_store': True,
                'hide_internal': True,
                'custom_hide': [],
                'custom_show': [],
                'important_vars': []
            }
            
            # Limpa os caches temporários do mod para evitar travamentos de memória
            wells_clear_caches()
            wells_log.info("Todas as configurações foram restauradas para os padrões", "DADOS")
    
    # Instancia o gerenciador de dados global utilizando o seu nick
    wells_data = WellsDataManager()

    ##################################################################
    #                FERRAMENTAS DE DESENVOLVEDOR DO WELLS           #
    ##################################################################
    
    class WellsDevTools:
        """Ferramentas de desenvolvedor para testes e depuração de erros (debug)"""
        
        @staticmethod
        def dump_menu_info(items):
            """Gera um relatório detalhado com as informações do menu atual"""
            menu_node, match_info = wells_menu_finder.find_menu_node(items)
            
            info = {
                'encontrado': menu_node is not None,
                'info_correspondencia': match_info,
                'total_itens': len(items),
            }
            
            if menu_node:
                info['info_no_codigo'] = {
                    'nome_arquivo': getattr(menu_node, 'filename', 'Não Disponível'),
                    'numero_linha': getattr(menu_node, 'linenumber', 0),
                    'total_itens_menu': len(menu_node.items) if hasattr(menu_node, 'items') else 0
                }
                
            return info
            
        @staticmethod
        def test_consequence_extraction(menu_node, choice_index):
            """Testa a extração de consequências para uma escolha específica do menu"""
            if not menu_node:
                return {'erro': 'Nenhum nó de menu foi fornecido'}
                
            try:
                consequences = wells_processor.process_choice(menu_node, choice_index, {'offset': 0})
                
                return {
                    'total': len(consequences),
                    'consequencias': [
                        {
                            'tipo': c.type,
                            'variavel': c.variable,
                            'valor': c.value,
                            'prioridade': c.get_priority()
                        }
                        for c in consequences
                    ]
                }
            except Exception as e:
                return {'erro': str(e)}
                
        @staticmethod
        def benchmark_menu_finding(iterations=100):
            """Mede o desempenho e a velocidade de busca do nó do menu"""
            import time
            
            # Este teste precisa de itens de menu reais ativos no jogo para funcionar
            return {
                'mensagem': 'O teste de desempenho requer um contexto de menu ativo no jogo',
                'iteracoes': iterations
            }
    
    # Instancia as ferramentas de desenvolvedor global utilizando o seu nick
    wells_dev = WellsDevTools()

    ##################################################################
    #                API PÚBLICA DO WELLS                            #
    ##################################################################
    
    # Funções públicas para o desenvolvedor usar nos botões e telas do menu
    
    def wells_enable():
        """Ativa o sistema de walkthrough do Wells"""
        persistent.wells_enabled = True
        wells_log.info("Sistema ativado via API", "API")
        
    def wells_disable():
        """Desativa o sistema de walkthrough do Wells"""
        persistent.wells_enabled = False
        wells_log.info("Sistema desativado via API", "API")
        
    def wells_toggle():
        """Alterna o estado do sistema entre ligado e desligado (Toggle)"""
        persistent.wells_enabled = not persistent.wells_enabled
        estado = "ativado" if persistent.wells_enabled else "desativado"
        wells_log.info(f"Sistema {estado} via API", "API")
        
    def wells_set_theme(theme_name):
        """Define o tema visual de exibição das dicas"""
        if theme_name in wells_formatter.THEMES:
            persistent.wells_theme = theme_name
            wells_log.info(f"Tema definido para '{theme_name}'", "API")
        else:
            wells_log.warn(f"Tema desconhecido: {theme_name}", "API")
            
    def wells_add_important_var(var_name):
        """Marca uma variável como importante para ser sempre exibida nas dicas"""
        if var_name not in persistent.wells_name_filters['important_vars']:
            persistent.wells_name_filters['important_vars'].append(var_name)
            
    def wells_hide_prefix(prefix):
        """Adiciona um prefixo de texto à lista de variáveis ocultadas"""
        if prefix not in persistent.wells_name_filters['custom_hide']:
            persistent.wells_name_filters['custom_hide'].append(prefix)
            
    def wells_show_prefix(prefix):
        """Adiciona um prefixo de texto para forçar a exibição de variáveis específicas"""
        if prefix not in persistent.wells_name_filters['custom_show']:
            persistent.wells_name_filters['custom_show'].append(prefix)

    ##################################################################
    #                INICIALIZAÇÃO FINAL DO WELLS                    #
    ##################################################################
    
    # Mensagens enviadas ao log e console de desenvolvimento ao carregar o módulo
    wells_log.info("Utilitários e extensões do Wells carregados com sucesso", "INICIALIZAÇÃO")
    print(f"[WELLS] Todos os módulos carregados com sucesso - Pronto para ajudar!")
    
init python:
    def wells_after_load():
        """Função chamada automaticamente pelo Ren'Py logo após o carregamento de um jogo salvo"""
        # Trava de segurança para limpar a sequência de menus de forma limpa sem dar travamento de memória
        if hasattr(store, 'wells_menu_finder') and hasattr(wells_menu_finder, 'reset_sequence'):
            wells_menu_finder.reset_sequence()
            wells_log.info("Sequência de menus restaurada após o carregamento do jogo", "CARREGAMENTO")
    
    # Registra a função na lista de retornos automáticos pós-carregamento do Ren'Py
    config.after_load_callbacks.append(wells_after_load)

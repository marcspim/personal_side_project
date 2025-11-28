# Versão 2.0 de Mim — HUD de Vida Gamificado

Este projeto é um **dashboard pessoal gamificado**, construído em **Streamlit**, que transforma sua rotina em um sistema de progressão de personagem com **níveis, XP, metas, perks, quests, badges e rastreamento de hábitos**.  
Ele funciona como um HUD de RPG aplicado ao mundo real, registrando tarefas e evolução em diversas áreas da vida.

---

## Objetivo do Projeto

Criar uma ferramenta intuitiva e motivadora para acompanhar desenvolvimento pessoal usando conceitos de:

- Gamificação  
- Habit tracking  
- Quantified Self  
- Monitoramento de metas  
- Sistema de progressão estilo RPG  

O projeto ainda está em **fase inicial**, mas já possui várias funcionalidades robustas e um banco de dados local.

---

## Tecnologias Utilizadas

- **Python 3.10+**
- **Streamlit**
- **SQLite**
- **Pandas / NumPy**
- **Plotly**
- **Hashlib**
- **Pathlib / datetime**

---

# Funcionalidades Principais

## Login e Sistema de Usuários
- Autenticação com hash SHA-256.  
- Perfis independentes por usuário.  
- Armazenamento isolado de eventos, metas, perks, quests e configurações.  
- Campos adicionais de perfil (bio, profissão, métricas corporais etc.).

---

## Registro de Atividades (XP)
- Registro de eventos contendo:
  - Data  
  - Área  
  - XP  
  - Tipo de evento  
  - Notas  
  - Usuário  
  - Associação opcional a uma meta  
- Cálculo automático do XP modificado por perks ativas.  
- Progressão de nível por fórmula exponencial:
  ```python
  BASE_XP = 100
  XP_EXP = 1.45
  ```

---

# Tipos de Evento

Cada evento possui um campo `type`, que classifica sua origem:

- `manual` – evento criado diretamente pelo usuário  
- `quest` – XP concedido pela conclusão de uma quest  
- `penalty` – XP negativo gerado automaticamente por penalidades  
- `meta` – XP inserido automaticamente a partir de metas (ex.: sugestão diária)  

Esse campo é utilizado para auditoria, transparência e análises mais precisas no dashboard.

---

# Visualizações e Métricas

- Gráfico de barras por área  
- Gráfico radar de equilíbrio  
- XP ao longo do tempo (diário, semanal, mensal)  
- Tabela completa de eventos  
- Sistema de badges:
  - +1000 XP  
  - +5000 XP  
  - Weekly Hero  
  - Consistência semanal  

---

# Metas (Tabela `metas`)

O sistema de metas é totalmente persistente e específico por usuário.

### Estrutura da Tabela `metas`

| Campo             | Descrição |
|-------------------|-----------|
| id                | Identificador |
| area              | Área da meta |
| weekly_target     | Meta semanal de XP |
| note              | Descrição detalhada |
| daily_suggestion  | Sugestão diária de XP (opcional) |
| active            | Indica se a meta está ativa |
| user              | Usuário dono da meta |
| created_at        | Timestamp de criação |
| updated_at        | Última atualização |

### Integração com o Registro de Eventos
Ao registrar um evento vinculado a uma meta, o campo `meta_id` é preenchido automaticamente.

### Progresso Semanal Automático
O sistema calcula:

- intervalo semanal ativo para cada meta  
- XP acumulado apenas para aquela meta  
- percentual concluído  
- barra de progresso normalizada  

### Registro Direto de XP para a Meta
Cada meta pode exibir um botão que registra XP diretamente:

- Se a meta possui `daily_suggestion`, esse valor é usado automaticamente
- O evento criado recebe `type='meta'`
- O campo `meta_id` é associado corretamente

Esse recurso permite cumprir metas diárias de forma rápida e consistente.

---

# Penalidades (Tabela `penalties`)

O sistema possui penalidades automáticas para hábitos não cumpridos.

### Estrutura da Tabela `penalties`

| Campo         | Descrição |
|---------------|-----------|
| id            | Identificador |
| name          | Nome da penalidade |
| area          | Área afetada |
| amount        | XP subtraído |
| user          | Usuário |
| created_at    | Timestamp |

Ao gerar uma penalidade, um evento é criado automaticamente com `type='penalty'` e XP negativo.

---

# Quests, Streaks e Gestão

O sistema de quests permite metas diárias, semanais ou únicas, com acompanhamento de streaks e recompensas em XP.

### Campos Internos

| Campo     | Descrição |
|-----------|-----------|
| title     | Título da quest |
| area      | Área relacionada |
| xp_reward | XP recebido ao concluir |
| cadence   | Frequência (`daily`, `weekly`, `once`) |
| last_done | Última conclusão |
| streak    | Dias/semana consecutivos completos |
| active    | Quest ativa ou desativada |
| user      | Usuário dono da quest |

### Lógica de Streak

- Se concluída no dia seguinte ao anterior, o streak aumenta  
- Caso contrário, reseta para 1  
- O campo `last_done` é atualizado automaticamente  

### Edição de Quests
O usuário pode editar:

- título  
- área  
- XP de recompensa  
- cadência  
- streak  

A edição é permitida apenas para:

- quests do próprio usuário  
- quests globais (`user IS NULL`)

### Exclusão de Quests (Desativação)
Quests não são removidas definitivamente.  
A exclusão é feita via:

```
active = 0
```

Isso preserva histórico e impede inconsistência em streaks.

---

# Sistema de Perks

Perks fornecem multiplicadores temporários de XP por área.

### Destaques do Sistema

- Perks são específicas por usuário ou globais  
- Podem expirar após `duration_days`  
- Aplicam sempre o maior multiplicador ativo  
- Matching por área é flexível (contains / listas separadas por "/")  
- O dashboard exibe tempo restante da perk

### Campos da Tabela `perks`

- name  
- area  
- unlock_level  
- effect  
- user  
- multiplier  
- duration_days  
- start_date  
- active  

---

# Estrutura Completa do Banco de Dados (SQLite)

O app cria ou atualiza automaticamente:

### Tabelas Principais

- `users`
- `events`
- `quests`
- `perks`
- `metas`
- `penalties`
- `user_config`

### Colunas Extras Garantidas por Migrações

- `events.meta_id`
- `perks.multiplier`
- `perks.duration_days`
- `perks.start_date`
- `perks.active`

---

# Importação e Exportação

- Exportação completa de eventos em CSV  
- Importação de eventos externos  
- Backup dos dados pessoais do usuário  

---

# Como Executar

Instalar dependências:

```bash
pip install streamlit pandas numpy plotly
```

Rodar o app:

```bash
streamlit run Versao2_Mim_streamlit_app.py
```

Acessar em:

```
http://localhost:8501
```

---

# Roadmap

- Modo multiplayer (ver progresso de outros usuários)
- Tema dark/light configurável
- Notificações push
- Sistema de "missões longas" com múltiplas etapas
- Integração com Google Calendar

---

# Contribuições

Como ainda está em fase inicial, qualquer sugestão, ideia, melhoria ou PR é muito bem-vinda!

---

# Licença

Uso pessoal privado. Pode ser adaptado conforme necessário.

---

# Autor

Projeto desenvolvido por Marcel Sarcinelli Pimenta, como ferramenta de produtividade gamificada e autoaperfeiçoamento.

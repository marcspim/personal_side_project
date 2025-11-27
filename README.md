# Versão 2.0 de Mim — HUD de Vida Gamificado  
**Status: FASE INICIAL / PROJETO EM DESENVOLVIMENTO**

Este projeto é um **dashboard pessoal gamificado**, construído em **Streamlit**, que transforma sua rotina em um sistema de progressão de personagem — com **níveis, XP, metas, perks, badges e quests**.  
Ele funciona como um HUD de RPG aplicado ao mundo real, registrando hábitos, tarefas e evolução em diversas áreas da vida.

---

## Objetivo do Projeto
Criar uma ferramenta simples, intuitiva e divertida para acompanhar desenvolvimento pessoal, usando conceitos de:
- Gamificação  
- Quantified Self  
- Monitoramento de metas  
- Habit tracking  
- Sistemas de progressão estilo RPG  

O projeto ainda está em **fase inicial**, mas já possui várias funcionalidades robustas e um banco de dados local.

---

## Tecnologias Utilizadas
- **Python 3.10+**
- **Streamlit**
- **SQLite (banco local)**
- **Pandas / NumPy**
- **Plotly (gráficos interativos)**
- **Hashlib (autenticação simples)**
- **Pathlib / datetime**

---

## Principais Funcionalidades

### Login e Sistema de Usuários
- Autenticação simples com hash SHA-256  
- Perfis de usuário independentes  
- Armazenamento de dados individualizados (eventos, quests, perks, configs)

---

### Registro de Atividades (XP)
- Registro de eventos com:
  - Data  
  - Área (ex: Produtividade, Educação, Saúde, Inglês etc.)  
  - XP  
  - Notas  
- Cálculo automático de:
  - XP total  
  - Nível atual  
  - XP necessário para o próximo nível  
- Progress bars e highlights visuais

---

### Visualizações e Métricas
- Gráfico de barras por área  
- Gráfico radar de equilíbrio de áreas  
- Evolução de XP ao longo do tempo (Diário/Semanal/Mensal)  
- Tabela completa de eventos  
- Sistema de badges:
  - +1000 XP  
  - +5000 XP  
  - Weekly Hero  
  - Consistência semanal  

---

### Metas (por área)

Metas possuem **persistência própria**, **associação com eventos** e **integração automática com quests diárias**.

#### Estrutura Interna
Cada meta é armazenada na tabela `metas` com os campos:

- `area` – área à qual a meta pertence  
- `weekly_target` – XP alvo semanal  
- `note` – descrição detalhada  
- `daily_suggestion` – sugestão de XP diário  
- `created_at` e `updated_at` – controles automáticos  
- `active` – permite arquivamento sem exclusão definitiva

#### Registro Automático de XP vinculado a metas
Ao registrar um evento, você pode vinculá-lo diretamente a uma meta.  
Esse vínculo cria uma relação `events.meta_id`, permitindo:

- cálculo correto da barra de progresso  
- métricas semanais baseadas na data de criação da meta  
- rastreamento específico (não misturado ao XP global)

#### Geração automática de Quests diárias
Se a meta tiver `daily_suggestion > 0`, o sistema cria ou atualiza automaticamente uma **quest diária** baseada nela:

- título: `Meta diária: <área>`  
- XP recompensa: igual à sugestão diária  
- cadência: diária  
- streak independente

Comportamento totalmente automatizado.

---

### Quests, Streaks e Regras Internas

As quests possuem lógica interna completa.

#### Campos importantes

- `cadence` — diária / semanal / única
- `last_done` — controla streak
- `streak` — número de dias/semana consecutivos
- `active` — permite desativar sem excluir
- `user` — quests específicas por usuário (ou globais via `NULL`)

#### Cálculo do Streak

Ao completar uma quest:
- se a última conclusão foi ontem, o streak aumenta
- senão, reseta para 1
- atualiza `last_done`

#### Quests globais vs. individuais

Quests com `user=NULL` são consideradas globais:
visíveis e completáveis por qualquer usuário.

Quests com `user=<username>` são específicas e só aparecem para ele.

---

### Penalidades
- Penalidade automática em caso de falhas em hábitos diários  
- Valor configurável  
- Subtração de XP gerando eventos de penalidade

---

### Perks (Desbloqueáveis)

#### Estrutura do Sistema de Perks
A tabela `perks` possui colunas avançadas:

- `multiplier` – multiplicador aplicado ao XP (ex.: 1.10, 1.20)  
- `duration_days` – duração em dias do efeito  
- `start_date` – quando a perk foi ativada  
- `active` – indica se o bônus está valendo  
- `user` – perks específicas por usuário (ou `NULL` para perks globais)

#### Regras de Ativação
Ao ativar uma perk:

- `start_date` = timestamp atual  
- `active = 1`  
- perks expiram automaticamente ao atingir `duration_days`

#### Aplicação automática de bônus de XP
Toda vez que um evento é registrado:

1. O sistema identifica perks ativas relevantes à **área** do evento.  
2. O maior multiplicador disponível é aplicado ao XP.  
3. A nota da atividade recebe um marcador:  

`[Bônus aplicado: original X → Y XP]`

Isso garante transparência total do sistema.

---

### Sistema de XP e Progressão de Nível

A progressão de nível não é linear.  
O app utiliza uma fórmula exponencial para calcular o XP necessário para cada nível:

```python
BASE_XP = 100
XP_EXP = 1.45
```

#### Consequências dessa fórmula

- níveis ficam progressivamente mais difíceis
- XP exigido cresce com uma curva suave
- o dashboard calcula:
  - nível atual
  - XP dentro do nível
  - XP total para o próximo nível
  - barra de progresso normalizada

Esse comportamento é automático e transparente ao usuário final.

---

### Edição, Exclusão e Regras de Autorização

O app possui ferramentas avançadas para manipulação de dados.

#### Edição de Eventos

É possível editar:
- `data`
- `área`
- `XP`
- `notas`

Com atualização imediata no banco.

#### Exclusão controlada

Eventos podem ser removidos, mas somente quando o usuário:
- habilita a exclusão manualmente
- confirma a operação

#### Edição e Exclusão de Metas

Ao excluir uma meta:
1. A meta é removida da tabela `metas`
2. Quests diárias vinculadas a ela também são excluídas
3. Configurações persistentes (`user_config`) são limpas automaticamente

#### Regras de Autorização

Para evitar interferência entre usuários:
- um usuário só pode editar quests e metas pertencentes a ele
- quests globais (`user IS NULL`) podem ser editadas, mas não modificam os dados de outro usuário
- eventos só podem ser editados/excluídos pelo dono

Esse modelo garante isolamento total dos dados pessoais.

---

### Importação / Exportação
- Exportar todos os eventos em CSV  
- Importar CSV externo  
- Backup total de dados pessoais

---

## Estrutura do Banco (SQLite)
O app cria automaticamente as tabelas:

- `users`
- `events`
- `quests`
- `perks`
- `user_config`

Tudo é armazenado localmente em:

`versao2_mim.db`

---

## ▶️ Como Executar

### 1. Instalar dependências

```bash
pip install streamlit pandas numpy plotly
```

### 2. Rodar o app

```bash
streamlit run Versao2_Mim_streamlit_app.py
```

### 3. Acessar no navegador

```
http://localhost:8501
```

Ou, caso queira permitir acesso na rede local:
```
streamlit run Versao2_Mim_streamlit_app.py --server.address 0.0.0.0
```

## Roadmap

- Sistema de XP bônus temporal (buffs de perks)
- Modo multiplayer (ver progresso de outros usuários)
- Tema dark/light configurável
- Notificações push
- Sistema de "missões longas" com múltiplas etapas
- Integração com Google Calendar

## Contribuições

Como ainda está em fase inicial, qualquer sugestão, ideia, melhoria ou PR é muito bem-vinda!

## Licença

A definir. Atualmente, uso pessoal privado.

## Autor

Projeto desenvolvido por Marcel Sarcinelli Pimenta, como ferramenta de produtividade gamificada e autoaperfeiçoamento.

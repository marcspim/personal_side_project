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
- Metas semanais e mensais  
- Salvas no banco (persistência automática)  
- Barra de progresso para cada meta  
- Suporte a múltiplas áreas personalizáveis

---

### Quests & Streaks
- Criação de quests com:
  - Título  
  - Área  
  - XP recompensa  
  - Cadência: diário / semanal / único  
- Streak automático  
- Registro de XP ao completar  
- Desativação de quests  
- Interface intuitiva para acompanhar o progresso

---

### Penalidades
- Penalidade automática em caso de falhas em hábitos diários  
- Valor configurável  
- Subtração de XP gerando eventos de penalidade

---

### Perks (Desbloqueáveis)
- Perks globais e específicos por usuário  
- Requisitos de nível por área  
- Efeitos personalizados  
- Exibição automática de perks desbloqueados e pendentes

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

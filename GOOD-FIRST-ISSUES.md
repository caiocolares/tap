# Guia de *good first issues*

Documento para **mantenedores**. Descreve como escrever uma issue de entrada que funcione — e por que ela é um artefato de engenharia, não um favor a iniciantes.

Por que existe: a `good first issue` é a porta de entrada de alunos e da comunidade no DTec OpenLabs. Issue mal escopada produz PR que precisa ser recusado, o que custa tempo de revisão e queima a primeira experiência de quem contribuiu. Issue bem escopada produz contribuição aproveitável **e** um contribuidor que volta.

---

## Os cinco requisitos

Uma issue só recebe o rótulo `good first issue` se cumprir todos:

1. **O caminho está apontado.** Arquivo e, se possível, função ou linha onde a mudança acontece. Quem está começando não conhece o repositório — descobrir *onde* mexer é o custo que a issue deve remover, não o desafio que ela deve propor.
2. **O critério de aceite é verificável.** "Melhorar o tratamento de erro" não serve. "Quando o arquivo de entrada estiver vazio, retornar 400 com a mensagem `arquivo vazio` em vez de 500" serve.
3. **Não depende de decisão de arquitetura.** Se a resposta correta exige escolher entre dois desenhos, a issue não é de entrada — é de discussão. Decida antes, registre em ADR, e só então abra a issue.
4. **Cabe em uma sessão.** Alvo de 1 a 4 horas para alguém que não conhece o código. Se for maior, quebre.
5. **Tem mantenedor responsável.** Uma pessoa nomeada para responder dúvidas e revisar o PR, com a meta de primeira resposta de 5 dias. Issue de entrada sem dono é promessa que o projeto não cumpre.

## Bons candidatos

- corrigir mensagem de erro imprecisa ou sem contexto;
- cobrir com teste um caminho de erro já identificado;
- validar entrada em um ponto único e bem delimitado;
- extrair valor fixo repetido para constante ou configuração;
- completar documentação de um comportamento que já existe;
- melhorar a saída de `--help` ou de um log confuso;
- adicionar caso a uma suíte de testes existente (mesmo formato, novo dado).

## Maus candidatos

- qualquer coisa que comece com "refatorar";
- primeira integração com serviço externo (exige credencial e ambiente);
- correção de bug que ainda não foi reproduzido;
- mudança que atravessa três camadas ou mais;
- tarefa cuja solução "correta" só existe na cabeça de um mantenedor;
- pendência de segurança — essas não passam por issue pública.

## Estrutura da issue

Use o template `03-good-first-issue.yml`, que pede exatamente estes campos:

```markdown
## Contexto
O que existe hoje e por que precisa mudar. Duas ou três frases.

## O que fazer
Passo a passo do que se espera. Sem escrever o código pela pessoa.

## Onde mexer
- `caminho/do/arquivo.py` — função `nome_da_funcao()`
- teste correspondente em `tests/test_arquivo.py`

## Critério de aceite
- [ ] comportamento verificável 1
- [ ] teste cobrindo o caso
- [ ] `<comando de teste>` passando

## Como rodar o projeto
Link para a seção do README. Não repita as instruções aqui — elas envelhecem em dois lugares.

## Dúvidas
Comente na issue e marque @mantenedor-responsavel. Pergunta de iniciante é bem-vinda:
está no nosso Código de Conduta, não é figura de linguagem.
```

## Rótulos

| Rótulo | Quando usar |
|---|---|
| `good first issue` | Cumpre os cinco requisitos acima |
| `help wanted` | Aberta a qualquer contribuidor, não necessariamente iniciante |
| `mentoria` | Mantenedor se compromete a acompanhar passo a passo |
| `aluno-unifor` | Especialmente adequada ao público acadêmico (recorte didático claro) |
| `triagem` | Ainda não avaliada — **nunca** combine com `good first issue` |

## Manutenção do estoque

- **Mantenha de 3 a 5 issues de entrada abertas** por projeto ativo. Repositório na vitrine sem porta de entrada não converte contribuidor.
- **Reserve por pessoa, não por fila.** Quem comenta "vou pegar essa" fica com ela; registre atribuindo a issue.
- **Libere após 14 dias sem atividade**, com um comentário cordial antes de reabrir para outras pessoas.
- **Revise o estoque a cada mês.** Issue de entrada que envelheceu — arquivo renomeado, comportamento já alterado — é pior que issue nenhuma.
- Quando a contribuição entrar, **agradeça no PR e registre o crédito**. Mentoria e revisão contam no reconhecimento da iniciativa tanto quanto autoria de código.

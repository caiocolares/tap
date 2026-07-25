# Como contribuir com o T.A.P. (Text & Audio Parser)

Obrigado pelo interesse. Este repositório é mantido pelo **DTec OpenLabs**, o braço open source da Diretoria de Tecnologia da Universidade de Fortaleza, e a contribuição é aberta: **você não precisa ter vínculo com a Unifor para contribuir.**

Ao participar, você concorda com o [Código de Conduta](CODE_OF_CONDUCT.md).

---

## Sumário

- [Formas de contribuir](#formas-de-contribuir)
- [Por onde começar](#por-onde-começar)
- [Fluxo de contribuição](#fluxo-de-contribuição)
- [Padrão de commit e o sign-off (DCO)](#padrão-de-commit-e-o-sign-off-dco)
- [O que o CI verifica](#o-que-o-ci-verifica)
- [Critérios de revisão](#critérios-de-revisão)
- [Prazos e o que esperar de nós](#prazos-e-o-que-esperar-de-nós)
- [Quem faz o merge](#quem-faz-o-merge)
- [Alunos da Unifor](#alunos-da-unifor)

---

## Formas de contribuir

Código não é a única contribuição que conta:

- corrigir bug ou implementar melhoria;
- **revisar Pull Request de outra pessoa** — vale tanto quanto abrir um;
- melhorar documentação, exemplo ou mensagem de erro;
- escrever teste para caminho ainda não coberto;
- reportar bug com passos claros de reprodução;
- discutir arquitetura nas issues.

## Por onde começar

1. Procure as issues [`good first issue`](../../issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) — são escopadas de propósito para uma primeira contribuição, com contexto, arquivos apontados e critério de aceite.
2. **Comente na issue antes de começar.** Um mantenedor confirma que ela está livre e tira dúvidas de escopo. Isso evita dois trabalhos paralelos na mesma coisa.
3. Não achou nada com sua cara? Abra uma issue de melhoria descrevendo a ideia antes de investir tempo em código.

Mudança grande (nova dependência, mudança de contrato público, refatoração ampla) **começa por issue de discussão**, não por PR. É frustrante para todos receber um PR de 800 linhas que precisa ser recusado por decisão de arquitetura.

## Fluxo de contribuição

```
fork  ──►  branch  ──►  commits assinados  ──►  PR  ──►  CI verde  ──►  review  ──►  merge (DTec)
```

1. Faça *fork* do repositório e crie uma branch a partir da `main`:

   ```bash
   git switch -c feat/descricao-curta
   ```

   Prefixos usados: `feat/`, `fix/`, `docs/`, `test/`, `refactor/`, `chore/`.

2. Rode os testes e o *lint* localmente antes de abrir o PR (comandos no [README](README.md#desenvolvimento)).

3. Abra o Pull Request preenchendo o template. PR pequeno e com escopo único é revisado muito mais rápido — se der para dividir, divida.

4. Responda aos comentários da revisão. Se algo não ficou claro, pergunte: revisão é conversa técnica, não julgamento.

## Padrão de commit e o sign-off (DCO)

Mensagem de commit no formato [Conventional Commits](https://www.conventionalcommits.org/pt-br/):

```
tipo(escopo opcional): resumo no imperativo, minúsculo, sem ponto final

Corpo opcional explicando o "por que", não o "o que" — o diff já mostra o quê.

Refs: #123
```

Tipos: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`, `chore`.

**Todo commit precisa do sign-off do DCO** (*Developer Certificate of Origin*), que é a declaração de que você tem o direito de contribuir aquele código:

```bash
git commit -s -m "fix: corrige contagem de itens vazios"
```

O `-s` acrescenta a linha `Signed-off-by: Seu Nome <seu@email>`. Esqueceu? Corrija com:

```bash
git commit --amend -s --no-edit      # último commit
git rebase --signoff origin/main     # vários commits
```

O texto integral está em [DCO](DCO). Configure `git config user.name` e `user.email` com dados reais — pseudônimo estável é aceito, e-mail descartável não.

> **Nota institucional.** O instrumento de titularidade das contribuições (DCO, e não CLA) é uma recomendação em validação com o Jurídico e o RH da Unifor. Enquanto essa validação não for concluída, o sign-off já é exigido — se o instrumento mudar, avisamos aqui e nas issues abertas.

## O que o CI verifica

Todo PR passa por:

| Verificação | O que barra |
|---|---|
| **Testes** | Falha de teste ou queda de cobertura no código alterado |
| **Lint / formatação** | Estilo fora do padrão do projeto |
| **Varredura de segredos** | Credencial, token ou chave no diff **e no histórico** |
| **Vulnerabilidades em dependências** | Dependência nova com CVE de severidade alta ou crítica |
| **SBOM** | Falha na geração do inventário de dependências |

As três últimas são **axioma do DTec OpenLabs**, não preferência do projeto: nenhum repositório da iniciativa opera sem elas.

Se o CI falhar por algo que você não entende, comente no PR. Não force *push* repetidamente tentando adivinhar.

## Critérios de revisão

O que a revisão olha, na ordem:

1. **Resolve o problema declarado?** Escopo do PR bate com a issue.
2. **Tem teste?** Correção de bug vem com teste que falha antes e passa depois.
3. **A dependência é necessária e é open source?** Toda dependência precisa ser open source — é critério de elegibilidade da iniciativa. Dependência nova exige justificativa no PR.
4. **É legível?** Nome, tamanho de função, comentário onde a intenção não é óbvia.
5. **Documentação acompanha?** Mudança de comportamento público atualiza o README.
6. **Nada sensível entrou?** Nem em código, nem em teste, nem em log de exemplo.

Sugestão de revisor não é ordem: se você discorda, argumente. Decisões de arquitetura que não se resolvem no PR sobem para uma issue de discussão e, se necessário, viram ADR em `docs/adr/`.

## Prazos e o que esperar de nós

- **Primeira resposta a PR: até 5 dias.** Essa é a métrica que a iniciativa acompanha mais de perto — PR externo sem resposta é a principal causa de morte de projeto open source institucional. Se passar de 5 dias, marque @dtec-openlabs/mantenedores no PR sem cerimônia.
- **Recusa vem com motivo.** Se a contribuição não entrar, você recebe a razão técnica registrada — nunca silêncio.
- **Crédito é público.** O histórico de commits preserva a autoria, e contribuição de revisão e mentoria é reconhecida junto com a de código.

## Quem faz o merge

Qualquer pessoa contribui, revisa e sugere. A **aprovação final na branch principal é exclusiva de integrantes ativos da DTec** com credencial `@unifor.br` (@dtec-openlabs/mantenedores) — é a soberania de merge da instituição sobre o que publica em seu nome. Não é uma barreira à contribuição: é a fronteira da responsabilidade institucional.

## Alunos da Unifor

Você é um dos públicos para quem esta iniciativa foi desenhada. O que a contribuição entrega:

- **Portfólio público real** — código resolvendo problema de verdade, no GitHub, com sua autoria preservada;
- **Mentoria direta** — revisão de código feita por profissionais e arquitetos da DTec, com feedback técnico, não apenas "aprovado";
- **Porta de entrada para a DTec** — a contribuição funciona como avaliação prática, *hands-on*.

Comece pelas [`good first issue`](../../issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) e diga na issue que é sua primeira contribuição — a revisão vem com mais contexto e menos pressa.

> **Ainda não prometemos horas de extensão nem peso em processo seletivo.** Essas duas contrapartidas dependem de acordo formal com as coordenações de curso, a instância de extensão e o RH da Unifor, e **ainda não estão pactuadas**. Quando estiverem, entram aqui de forma explícita. Preferimos não prometer a prometer e não cumprir.

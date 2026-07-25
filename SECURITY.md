# Política de Segurança

## Reportando uma vulnerabilidade

**Não abra issue pública para vulnerabilidade.** Issue é visível para todo mundo, inclusive para quem exploraria a falha antes da correção.

Use um destes canais privados:

1. **GitHub Security Advisory** (preferido) — [abrir relato privado](https://github.com/dtec-openlabs/tap/security/advisories/new). Fica registrado no próprio repositório e permite discussão privada com os mantenedores.
2. **E-mail** — **opensource@unifor.br**.

Se puder, inclua no relato:

- tipo de vulnerabilidade e o impacto que você identificou;
- versão, *commit* ou *tag* afetados;
- passos de reprodução, PoC ou requisição de exemplo;
- configuração necessária para reproduzir.

Relato em português ou inglês, tanto faz.

## O que esperar

| Etapa | Prazo alvo |
|---|---|
| Confirmação de recebimento | 5 dias úteis |
| Avaliação inicial e classificação de severidade | 10 dias úteis |
| Correção ou plano de correção com prazo | conforme severidade, informado na avaliação |

Manteremos você informado ao longo da análise. Se o relato for considerado inválido, você recebe a razão técnica — não silêncio.

## Divulgação coordenada

Pedimos que a falha não seja divulgada publicamente até que exista correção disponível ou até que decidamos, em conjunto, o contrário. Ao publicar a correção:

- creditamos quem reportou, se essa pessoa quiser o crédito;
- publicamos o *advisory* com descrição, versões afetadas e versão corrigida.

Não operamos programa de *bug bounty* — não há pagamento por relato. O reconhecimento é público e, quando aplicável, segue o modelo de reconhecimento do DTec OpenLabs (em bem ou serviço, nunca em espécie).

## Versões suportadas

| Versão | Suportada |
|---|---|
| <!-- ex.: 1.x --> | ✅ |
| <!-- ex.: 0.x --> | ❌ |

## Escopo

**Dentro do escopo:** o código deste repositório e suas configurações de build, CI e empacotamento.

**Fora do escopo:** infraestrutura da Universidade de Fortaleza, sistemas institucionais, e vulnerabilidades em dependências de terceiros — estas devem ser reportadas ao projeto de origem (avise-nos também, para que possamos atualizar ou mitigar).

Vulnerabilidade em sistema institucional da Unifor que não seja este repositório deve ser reportada aos canais da Diretoria de Tecnologia, não aqui.

## Como este projeto se previne

Todo Pull Request e a branch principal passam por, no CI:

- **varredura de segredos**, sobre o diff **e sobre o histórico completo** do repositório;
- **varredura de vulnerabilidades em dependências**, barrando severidade alta e crítica;
- **geração e publicação de SBOM** (inventário de dependências, formato CycloneDX);
- atualização automatizada de dependências por Dependabot.

Isso é axioma da iniciativa DTec OpenLabs, não configuração opcional deste repositório.

### Se um segredo foi commitado

Rotacione primeiro, limpe depois. Um segredo que já esteve em repositório público deve ser considerado comprometido, mesmo que o *commit* tenha sido reescrito — assuma que foi coletado.

1. **Revogue e rotacione a credencial imediatamente** na origem (provedor, cofre, serviço).
2. Avise **opensource@unifor.br**.
3. Só então trate o histórico do repositório, com apoio dos mantenedores.

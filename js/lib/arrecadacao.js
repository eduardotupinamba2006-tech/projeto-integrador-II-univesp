// Somas de arrecadação para os painéis. Considera só pagamentos confirmados (status "pago").

function centavos(valor) {
  return Math.round(Number(valor) * 100);
}

export function somarArrecadacao(pagamentos) {
  const soma = { dizimo: 0, taxa_certidao: 0 };
  for (const p of pagamentos) {
    if (p.status === 'pago' && p.tipo in soma) soma[p.tipo] += centavos(p.valor);
  }
  return {
    dizimo: soma.dizimo / 100,
    taxa_certidao: soma.taxa_certidao / 100,
    total: (soma.dizimo + soma.taxa_certidao) / 100,
  };
}

export function arrecadacaoPorParoquia(pagamentos, paroquias) {
  return paroquias
    .map((paroquia) => ({
      paroquia,
      ...somarArrecadacao(pagamentos.filter((p) => p.paroquia_id === paroquia.id)),
    }))
    .sort((a, b) => a.paroquia.nome.localeCompare(b.paroquia.nome, 'pt-BR'));
}

// Agrupa por mês ("2026-09") em ordem cronológica, usando a data de criação do pagamento.
export function arrecadacaoPorMes(pagamentos) {
  const meses = new Map();
  for (const p of pagamentos) {
    if (p.status !== 'pago') continue;
    const mes = String(p.criado_em).slice(0, 7);
    if (!meses.has(mes)) meses.set(mes, []);
    meses.get(mes).push(p);
  }
  return [...meses.keys()].sort().map((mes) => ({ mes, ...somarArrecadacao(meses.get(mes)) }));
}

export function contarSolicitacoes(solicitacoes) {
  const contagem = { total: solicitacoes.length, aguardando_pagamento: 0, em_analise: 0, aprovado: 0, rejeitado: 0 };
  for (const s of solicitacoes) contagem[s.status] += 1;
  return contagem;
}

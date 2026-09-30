// Componente de escolha de paróquia com busca por nome e por proximidade.
// Com a chave do Google Maps configurada, ganha a busca a partir de um endereço ou CEP
// e um mapa com as paróquias; sem ela, fica só a lista e a localização do navegador.
import { config, supabase } from './supabase.js';
import { filtrarPorNome, formatarDistancia, ordenarPorProximidade } from './lib/geo.js';
import { escaparHtml } from './lib/formatacao.js';
import { MAP_ID, carregarGoogleMaps, geocodificar } from './mapa.js';

export async function montarEscolhaParoquia(container, { legenda = 'Paróquia', aoEscolher = () => {} } = {}) {
  const comMapa = Boolean(config.googleMapsKey);
  container.innerHTML = `
    <fieldset>
      <legend>${escaparHtml(legenda)}</legend>
      <div class="campo">
        <label for="busca-paroquia">Buscar por nome ou endereço</label>
        <input type="search" id="busca-paroquia" autocomplete="off">
      </div>
      ${comMapa ? `
      <div class="campo">
        <label for="endereco-origem">Paróquias perto de um endereço ou CEP</label>
        <div class="acoes">
          <input type="text" id="endereco-origem" autocomplete="street-address">
          <button type="button" class="botao botao-secundario" id="buscar-endereco"><i class="ph-light ph-map-pin" aria-hidden="true"></i>Buscar</button>
        </div>
      </div>` : ''}
      <div class="acoes">
        <button type="button" class="botao botao-secundario" id="usar-localizacao"><i class="ph-light ph-navigation-arrow" aria-hidden="true"></i>Mais próximas de mim</button>
      </div>
      <p class="dica" id="status-paroquias" role="status" aria-live="polite"></p>
      <div class="lista-paroquias" id="lista-paroquias"></div>
      ${comMapa ? '<div class="mapa" id="mapa-paroquias" role="region" aria-label="Mapa das paróquias"></div>' : ''}
    </fieldset>`;

  const busca = container.querySelector('#busca-paroquia');
  const lista = container.querySelector('#lista-paroquias');
  const status = container.querySelector('#status-paroquias');
  const botaoLocal = container.querySelector('#usar-localizacao');

  const { data, error } = await supabase
    .from('paroquias')
    .select('id, nome, endereco, lat, lng, dioceses(nome)')
    .order('nome');
  if (error) {
    status.textContent = 'Não foi possível carregar as paróquias. Recarregue a página.';
    return null;
  }

  let paroquias = data;
  let escolhida = null;
  let mapa = null;

  function desenhar() {
    const visiveis = filtrarPorNome(paroquias, busca.value);
    if (!visiveis.length) {
      lista.innerHTML = '<p>Nenhuma paróquia encontrada.</p>';
      return;
    }
    lista.innerHTML = visiveis.map((p) => `
      <label class="opcao">
        <input type="radio" name="paroquia" value="${p.id}" ${escolhida === p.id ? 'checked' : ''}>
        <span>
          <strong>${escaparHtml(p.nome)}</strong>
          ${p.distanciaKm != null ? `<span class="etiqueta">${formatarDistancia(p.distanciaKm)}</span>` : ''}
          <span class="dica">${escaparHtml(p.endereco)} · ${escaparHtml(p.dioceses?.nome || '')}</span>
        </span>
      </label>`).join('');
  }

  function escolher(id) {
    escolhida = id;
    aoEscolher(paroquias.find((p) => p.id === escolhida));
    mapa?.destacar(id);
  }

  function ordenarAPartirDe(origem, descricao) {
    paroquias = ordenarPorProximidade(paroquias, origem);
    desenhar();
    status.textContent = `Paróquias ordenadas pela distância ${descricao}.`;
    // O mapa enquadra o ponto de partida e até 3 paróquias a menos de 30 km (ou só a mais próxima).
    const comDistancia = paroquias.filter((p) => p.distanciaKm != null);
    const perto = comDistancia.filter((p) => p.distanciaKm <= 30).slice(0, 3);
    mapa?.mostrarOrigem(origem, perto.length ? perto : comDistancia.slice(0, 1));
  }

  lista.addEventListener('change', (evento) => escolher(evento.target.value));

  busca.addEventListener('input', desenhar);

  botaoLocal.addEventListener('click', () => {
    if (!navigator.geolocation) {
      status.textContent = 'Seu navegador não informa a localização. Use a busca por nome ou endereço.';
      return;
    }
    status.textContent = 'Obtendo sua localização…';
    navigator.geolocation.getCurrentPosition(
      (pos) => ordenarAPartirDe({ lat: pos.coords.latitude, lng: pos.coords.longitude }, 'até você'),
      () => { status.textContent = 'Não foi possível obter sua localização. Use a busca por nome ou endereço.'; },
      { timeout: 10000 },
    );
  });

  desenhar();

  if (comMapa) {
    // O mapa carrega em segundo plano: a página não espera o Google para ficar utilizável.
    montarMapa(container, paroquias, {
      aoClicar: (id) => {
        // O marcador escolhe a mesma paróquia que o rádio da lista.
        busca.value = '';
        desenhar();
        const radio = lista.querySelector(`input[value="${id}"]`);
        radio.checked = true;
        radio.focus();
        escolher(id);
      },
      aoFalhar: () => {
        container.querySelector('#mapa-paroquias')?.remove();
        container.querySelector('#endereco-origem')?.closest('.campo').remove();
        mapa = null;
      },
    }).then((m) => { mapa = m; });

    const campoEndereco = container.querySelector('#endereco-origem');
    const buscarEndereco = async () => {
      const texto = campoEndereco?.value.trim();
      if (!texto) return;
      if (!mapa) {
        status.textContent = 'O mapa ainda está carregando. Tente de novo em instantes.';
        return;
      }
      status.textContent = 'Procurando o endereço…';
      let origem;
      try {
        origem = await geocodificar(mapa.maps, texto);
      } catch {
        status.textContent = 'A busca por endereço está indisponível no momento. Use a busca por nome ou "Mais próximas de mim".';
        return;
      }
      if (!origem) {
        status.textContent = 'Endereço não encontrado. Confira o texto ou tente o CEP.';
        return;
      }
      ordenarAPartirDe(origem, `até ${origem.descricao}`);
    };
    container.querySelector('#buscar-endereco')?.addEventListener('click', buscarEndereco);
    campoEndereco?.addEventListener('keydown', (evento) => {
      // Enter busca o endereço em vez de enviar o formulário da página.
      if (evento.key === 'Enter') {
        evento.preventDefault();
        buscarEndereco();
      }
    });
  }

  return {
    paroquias: () => paroquias,
    escolhida: () => paroquias.find((p) => p.id === escolhida) || null,
    ordenarAPartirDe,
  };
}

// Mapa com um marcador por paróquia. Devolve null (e chama aoFalhar) se o Google Maps não carregar.
async function montarMapa(container, paroquias, { aoClicar, aoFalhar }) {
  const elemento = container.querySelector('#mapa-paroquias');
  const falhar = () => { aoFalhar(); return null; };
  document.addEventListener('google-maps-falhou', aoFalhar, { once: true });

  let maps, MapaGoogle, AdvancedMarkerElement, PinElement;
  try {
    maps = await carregarGoogleMaps(config.googleMapsKey);
    ({ Map: MapaGoogle } = await maps.importLibrary('maps'));
    ({ AdvancedMarkerElement, PinElement } = await maps.importLibrary('marker'));
  } catch {
    return falhar();
  }

  const comCoordenada = paroquias.filter((p) => p.lat != null && p.lng != null);
  if (!comCoordenada.length) return falhar();

  const mapa = new MapaGoogle(elemento, {
    mapId: MAP_ID,
    center: { lat: Number(comCoordenada[0].lat), lng: Number(comCoordenada[0].lng) },
    zoom: 12,
    streetViewControl: false,
    mapTypeControl: false,
  });

  const limites = new maps.LatLngBounds();
  const marcadores = new Map();
  for (const p of comCoordenada) {
    const posicao = { lat: Number(p.lat), lng: Number(p.lng) };
    const marcador = new AdvancedMarkerElement({ map: mapa, position: posicao, title: p.nome, gmpClickable: true });
    marcador.addListener('click', () => aoClicar(p.id));
    marcadores.set(p.id, { marcador, posicao });
    limites.extend(posicao);
  }
  if (comCoordenada.length > 1) mapa.fitBounds(limites, 40);

  let origem = null;
  return {
    maps,
    destacar(id) {
      for (const [chave, { marcador }] of marcadores) {
        marcador.content = chave === id ? new PinElement({ scale: 1.3, background: '#1e3a8a', borderColor: '#1e3a8a', glyphColor: '#ffffff' }).element : null;
      }
      const alvo = marcadores.get(id);
      if (alvo) mapa.panTo(alvo.posicao);
    },
    mostrarOrigem(ponto, proximas) {
      if (origem) origem.map = null;
      const pino = new PinElement({ background: '#ffffff', borderColor: '#1e3a8a', glyphColor: '#1e3a8a' });
      // O ponto de partida só indica a posição: não pode cobrir o clique nos marcadores das paróquias.
      pino.element.style.pointerEvents = 'none';
      origem = new AdvancedMarkerElement({ map: mapa, position: ponto, title: 'Ponto de partida', content: pino.element, zIndex: -1 });
      const area = new maps.LatLngBounds(ponto, ponto);
      for (const p of proximas) area.extend(marcadores.get(p.id)?.posicao ?? ponto);
      mapa.fitBounds(area, 60);
    },
  };
}

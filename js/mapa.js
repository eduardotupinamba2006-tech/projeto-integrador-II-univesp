// Carregamento sob demanda do Google Maps JavaScript API (mapa e geocodificação).
// A chave vem de /api/config e é restrita por domínio no Google Cloud; sem ela,
// a escolha de paróquia continua funcionando só com a lista e a localização do navegador.

// Map ID de demonstração do Google, exigido pelos marcadores avançados.
export const MAP_ID = 'DEMO_MAP_ID';

let carregamento = null;

export function carregarGoogleMaps(chave) {
  if (!carregamento) {
    carregamento = new Promise((resolve, reject) => {
      window.__googleMapsPronto = () => resolve(window.google.maps);
      // Chamado pelo Google quando a chave é inválida ou o domínio não está autorizado.
      window.gm_authFailure = () => {
        document.dispatchEvent(new CustomEvent('google-maps-falhou'));
        reject(new Error('Chave do Google Maps recusada.'));
      };
      const script = document.createElement('script');
      const parametros = new URLSearchParams({
        key: chave,
        loading: 'async',
        language: 'pt-BR',
        region: 'BR',
        callback: '__googleMapsPronto',
      });
      script.src = `https://maps.googleapis.com/maps/api/js?${parametros}`;
      script.async = true;
      script.onerror = () => reject(new Error('Não foi possível carregar o Google Maps.'));
      document.head.append(script);
    });
  }
  return carregamento;
}

// Converte um endereço ou CEP em coordenadas. Devolve null se nada for encontrado.
export async function geocodificar(maps, endereco) {
  const { Geocoder } = await maps.importLibrary('geocoding');
  try {
    const { results } = await new Geocoder().geocode({ address: endereco, region: 'br' });
    if (!results.length) return null;
    const local = results[0].geometry.location;
    return { lat: local.lat(), lng: local.lng(), descricao: results[0].formatted_address };
  } catch {
    return null;
  }
}

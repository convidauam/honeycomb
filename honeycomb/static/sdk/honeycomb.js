// SDK homologado para que los videojuegos hablen con la API de Honeycomb.
// Uso:
//   const hc = await Honeycomb.connect();
//   hc.user;                                   // {userid, displayname, username, icon, background,
//                                               //  identities: [{kind, value}, ...], can_share}
//   const data = await hc.load(nodeId);         // {interactions, stats, preferences, badges, ...}
//   await hc.save(nodeId, { stats: {...}, preferences: {...} });
//   await hc.awardBadge(nodeId, { id: 'high-score-100', title: 'Cien puntos', icon: '🏆' });
//   const mine = await hc.achievements();        // {achievements: [{id, title, icon, nodeid, ...}]}
//   if (hc.user.can_share) await hc.share(nodeId, 'high-score-100'); // publica el logro al Fediverso
//   // El usuario pudo entrar por el Fediverso, por usuario/contrasena, o ambos si los vinculo desde
//   // /cuenta -- can_share solo es true cuando hay una identidad del Fediverso vinculada Y un token
//   // de publicacion guardado (honeycomb.token_encryption_key configurada en el servidor).
window.Honeycomb = (function () {
  var API_BASE = '/api/v1';

  function detectNodeId() {
    var params = new URLSearchParams(window.location.search);
    if (params.has('nodeid')) return params.get('nodeid');
    var script = document.currentScript;
    if (script && script.dataset && script.dataset.nodeId) return script.dataset.nodeId;
    return null;
  }

  function request(path, options) {
    var opts = Object.assign({
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
    }, options);
    return fetch(API_BASE + path, opts).then(function (response) {
      if (!response.ok) {
        var error = new Error('Honeycomb API error ' + response.status);
        error.status = response.status;
        throw error;
      }
      return response.json();
    });
  }

  function HoneycombSession(user, nodeId) {
    this.user = user;
    this.nodeId = nodeId || null;
  }

  HoneycombSession.prototype.load = function (nodeId) {
    var id = nodeId || this.nodeId;
    if (!id) return Promise.reject(new Error('Honeycomb: nodeId is required'));
    return request('/sipping/' + encodeURIComponent(id));
  };

  HoneycombSession.prototype.save = function (nodeId, data) {
    var id = nodeId;
    var payload = data;
    if (typeof nodeId === 'object') {
      payload = nodeId;
      id = this.nodeId;
    }
    if (!id) return Promise.reject(new Error('Honeycomb: nodeId is required'));
    return request('/sipping/' + encodeURIComponent(id), {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    });
  };

  HoneycombSession.prototype.awardBadge = function (nodeId, badge) {
    var id = nodeId;
    var payload = badge;
    if (typeof nodeId === 'object') {
      payload = nodeId;
      id = this.nodeId;
    }
    if (!id) return Promise.reject(new Error('Honeycomb: nodeId is required'));
    return request('/sipping/' + encodeURIComponent(id) + '/badges', {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    });
  };

  HoneycombSession.prototype.achievements = function () {
    return request('/achievements');
  };

  HoneycombSession.prototype.share = function (nodeId, badgeId, message) {
    var id = nodeId || this.nodeId;
    if (!id) return Promise.reject(new Error('Honeycomb: nodeId is required'));
    var payload = { nodeid: id, badge_id: badgeId };
    if (message) payload.message = message;
    return request('/share', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  };

  function connect(nodeId) {
    return request('/me').then(function (user) {
      return new HoneycombSession(user, nodeId || detectNodeId());
    });
  }

  return { connect: connect };
})();

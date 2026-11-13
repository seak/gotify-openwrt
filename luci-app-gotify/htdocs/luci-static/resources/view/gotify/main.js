'use strict';
'require view';
'require form';
'require rpc';
'require ui';

var callGetConfig = rpc.declare({
	object: 'luci.gotify',
	method: 'get_config',
	expect: {}
});

var callSetConfig = rpc.declare({
	object: 'luci.gotify',
	method: 'set_config',
	params: ['port', 'listen_addr', 'loglevel', 'registration', 'wan_access', 'restart'],
	expect: {}
});

var callService = rpc.declare({
	object: 'luci.gotify',
	method: 'service',
	params: ['action'],
	expect: {}
});

function webUiUrl(port) {
	var p = parseInt(port, 10);
	if (!isFinite(p) || p < 1 || p > 65535)
		p = 8080;
	return 'http://' + window.location.hostname + ':' + p + '/';
}

function asFlag(v) {
	return (v === true || v === '1' || v === 1 || v === 'true') ? '1' : '0';
}

return view.extend({
	load: function () {
		return callGetConfig();
	},

	render: function (data) {
		var cfg = data || {};
		var formdata = {
			main: {
				port: String(cfg.port || '8080'),
				listen_addr: cfg.listen_addr || '',
				loglevel: cfg.loglevel || 'info',
				registration: asFlag(cfg.registration),
				wan_access: asFlag(cfg.wan_access)
			}
		};

		var m = new form.JSONMap(formdata, _('Gotify'),
			_('Manage the Gotify push notification service. Apps, clients, and messages stay in the Gotify Web UI. Database and image paths are fixed by the package init script.'));

		var s = m.section(form.NamedSection, 'main', 'gotify', _('Service'));

		var o = s.option(form.DummyValue, '_running', _('Running'));
		o.cfgvalue = function () {
			return cfg.running ? _('Yes') : _('No');
		};

		o = s.option(form.DummyValue, '_enabled', _('Start on boot'));
		o.cfgvalue = function () {
			return cfg.enabled ? _('Yes') : _('No');
		};

		o = s.option(form.DummyValue, '_link', _('Gotify Web UI'));
		o.rawhtml = true;
		o.cfgvalue = function () {
			var url = webUiUrl(formdata.main.port || cfg.port || 8080);
			return '<a href="%s" target="_blank" rel="noopener">%s</a>'.format(url, url);
		};

		o = s.option(form.Button, '_start', _('Start'));
		o.inputtitle = _('Start');
		o.inputstyle = 'action';
		o.onclick = function (ev) {
			ev.preventDefault();
			return callService('start').then(function () {
				location.reload();
			});
		};

		o = s.option(form.Button, '_stop', _('Stop'));
		o.inputtitle = _('Stop');
		o.inputstyle = 'remove';
		o.onclick = function (ev) {
			ev.preventDefault();
			return callService('stop').then(function () {
				location.reload();
			});
		};

		o = s.option(form.Button, '_enable', _('Enable on boot'));
		o.inputtitle = _('Enable');
		o.inputstyle = 'apply';
		o.onclick = function (ev) {
			ev.preventDefault();
			return callService('enable').then(function () {
				location.reload();
			});
		};

		o = s.option(form.Button, '_disable', _('Disable on boot'));
		o.inputtitle = _('Disable');
		o.inputstyle = 'reset';
		o.onclick = function (ev) {
			ev.preventDefault();
			return callService('disable').then(function () {
				location.reload();
			});
		};

		o = s.option(form.Value, 'port', _('Port'));
		o.datatype = 'port';
		o.rmempty = false;

		o = s.option(form.Value, 'listen_addr', _('Listen address'));
		o.placeholder = _('empty = all addresses');
		o.rmempty = true;

		o = s.option(form.ListValue, 'loglevel', _('Log level'));
		o.value('debug', 'debug');
		o.value('info', 'info');
		o.value('warning', 'warning');
		o.value('error', 'error');
		o.value('fatal', 'fatal');

		o = s.option(form.Flag, 'registration', _('Allow registration'));
		o.rmempty = false;
		o.default = '0';

		o = s.option(form.Flag, 'wan_access', _('Allow WAN access (firewall)'));
		o.description = _('WAN TCP accept rule for the Gotify port. Off by default; does not change the Gotify package itself.');
		o.rmempty = false;
		o.default = '0';

		m.save = function () {
			return m.parse().then(function () {
				var main = formdata.main || {};
				return callSetConfig(
					String(main.port || '8080'),
					String(main.listen_addr || ''),
					String(main.loglevel || 'info'),
					asFlag(main.registration) === '1' ? 'true' : 'false',
					asFlag(main.wan_access) === '1' ? 'true' : 'false',
					'true'
				).then(function () {
					ui.addNotification(null, E('p', _('Configuration saved and service restarted.')), 'info');
				});
			});
		};

		return m.render().then(L.bind(function (node) {
			this.map = m;
			return node;
		}, this));
	},

	handleSave: function (ev) {
		return this.map.save();
	},

	handleSaveApply: function (ev, mode) {
		return this.handleSave(ev);
	}
});

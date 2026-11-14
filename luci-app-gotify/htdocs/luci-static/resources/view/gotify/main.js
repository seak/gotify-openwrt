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

var callSetEnv = rpc.declare({
	object: 'luci.gotify',
	method: 'set_env',
	params: ['content', 'restart'],
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
			},
			env: {
				content: cfg.env_content || ''
			}
		};

		var m = new form.JSONMap(formdata, _('Gotify Server'),
			_('Manage the Gotify Server push notification service. Apps, clients, and messages stay in the Gotify Server Web UI. Database and image paths are fixed by the package init script.'));

		var s = m.section(form.NamedSection, 'main', 'gotify', _('Service'));

		var o = s.option(form.DummyValue, '_link', _('Gotify Server Web UI'));
		o.rawhtml = true;
		o.cfgvalue = function () {
			var url = webUiUrl(formdata.main.port || cfg.port || 8080);
			return '<a href="%s" target="_blank" rel="noopener">%s</a>'.format(url, url);
		};

		var svcStatus = cfg.running ? _('Start') : _('Stop');
		o = s.option(form.Button, '_svc',
			_('Service status Start/Stop (current status: %s)').format(svcStatus));
		o.inputtitle = cfg.running ? _('Stop') : _('Start');
		o.inputstyle = cfg.running ? 'remove' : 'action';
		o.onclick = function (ev) {
			ev.preventDefault();
			return callService(cfg.running ? 'stop' : 'start').then(function () {
				location.reload();
			});
		};

		var bootStatus = cfg.enabled ? _('Enable') : _('Disable');
		o = s.option(form.Button, '_boot',
			_('Start on boot Enable/Disable (current status: %s)').format(bootStatus));
		o.inputtitle = cfg.enabled ? _('Disable') : _('Enable');
		o.inputstyle = cfg.enabled ? 'reset' : 'apply';
		o.onclick = function (ev) {
			ev.preventDefault();
			return callService(cfg.enabled ? 'disable' : 'enable').then(function () {
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
		o.value('info', _('info (default)'));
		o.value('warning', 'warning');
		o.value('error', 'error');
		o.value('fatal', 'fatal');

		o = s.option(form.Flag, 'registration', _('Allow new user registration'));
		o.rmempty = false;
		o.default = '0';

		o = s.option(form.Flag, 'wan_access', _('Allow WAN access (firewall)'));
		o.description = _('WAN TCP accept rule for the Gotify Server port. Off by default; does not change the Gotify Server package itself.');
		o.rmempty = false;
		o.default = '0';

		var sEnv = m.section(form.NamedSection, 'env', 'env', _('Configuration file'));
		sEnv.description = _('/etc/gotify/server.env — edit directly; data paths remain forced by the init script.');

		o = sEnv.option(form.TextValue, 'content', _('File contents'));
		o.rows = 18;
		o.monospace = true;
		o.rmempty = true;

		o = sEnv.option(form.Button, '_save_env', _('Save file'));
		o.inputtitle = _('Save file');
		o.inputstyle = 'apply';
		o.onclick = L.bind(function (ev) {
			ev.preventDefault();
			return m.parse().then(function () {
				var content = (formdata.env && formdata.env.content != null)
					? String(formdata.env.content) : '';
				return callSetEnv(content, 'true').then(function () {
					ui.addNotification(null, E('p', _('Configuration file saved and service restarted.')), 'info');
					location.reload();
				});
			});
		}, this);

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

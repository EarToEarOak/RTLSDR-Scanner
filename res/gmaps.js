/*
 * rtlsdr_scan
 *
 * http://eartoearoak.com/software/rtlsdr-scanner
 *
 * Copyright 2012 - 2015 Al Brown
 *
 * A frequency scanning GUI for the OsmoSDR rtl-sdr library at
 * http://sdr.osmocom.org/trac/wiki/rtl-sdr
 *
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, or (at your option)
 * any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 */

Ext.Loader.setConfig({
	enabled : true,
	disableCaching : false,
	paths : {
		GeoExt : "http://geoext.github.com/geoext2/src/GeoExt/",
		Ext : "http://cdn.sencha.com/ext/gpl/4.2.1/src"
	}
});

Ext.require([ 'Ext.container.Viewport', 'Ext.layout.container.Border',
		'GeoExt.tree.Panel', 'Ext.tree.plugin.TreeViewDragDrop',
		'GeoExt.panel.Map', 'GeoExt.tree.OverlayLayerContainer',
		'GeoExt.tree.BaseLayerContainer', 'GeoExt.data.LayerTreeModel',
		'GeoExt.tree.View', 'GeoExt.tree.Column' ]);

var map;
var heatmap;
var layers = [];

var points = [];
var lastPoint;

var markersLocation = [];
var markersLast = [];

var refresh = 5000;
var refreshTimeout;
var isRefreshing = true;

var overlay = {
	last : true,
	locations : true,
	heatmap : true
};

var follow = {
	last : true,
	locations : true
};

var projGps = new OpenLayers.Projection('EPSG:4326');
var projSm = new OpenLayers.Projection('EPSG:900913');

var worker;

var margins = '0 0 0 5';

Ext.application({
	name : 'RTLSDR Scanner',
	launch : function() {

		setupMap();
		setupLayers();

		var mapPanel = Ext.create('GeoExt.panel.Map', {
			title : 'RTLSDR Scanner',
			region : 'center',
			map : map,
			layers : layers
		});

		var store = Ext.create('Ext.data.TreeStore', {
			model : 'GeoExt.data.LayerTreeModel',
			root : {
				text : 'RTLSDR Scanner',
				expanded : true,
				children : [ {
					text : "Maps",
					plugins : [ 'gx_baselayercontainer' ],
					expanded : true,
				}, {
					text : 'Overlays',
					expanded : true,
					children : [ {
						text : 'Last Location',
						checked : overlay.last,
						leaf : true,
						id : 'overlayLast',
					}, {
						text : 'Locations',
						checked : overlay.locations,
						leaf : true,
						id : 'overlayLoc'
					}, {
						text : 'Location Heatmap',
						checked : overlay.heatmap,
						leaf : true,
						id : 'overlayHeat'
					} ]
				} ],
			}
		});

		var layersPanel = Ext.create('GeoExt.tree.Panel', {
			border : false,
			title : "Layers",
			width : '100%',
			collapsible: true,
			store : store,
			listeners : {
				checkchange : checkOverlay
			}
		});

		var infoPanel = Ext.create('Ext.Panel', {
			border : false,
			layout : 'vbox',
			title : 'Info',
			width : '100%',
			collapsible: true,
			items : [ {
				xtype : 'displayfield',
				id : 'dispLocs',
				fieldLabel : 'Locations',
				margins : margins
			}, {
				xtype : 'displayfield',
				id : 'dispCoords',
				fieldLabel : 'Last location',
				margins : margins
			} ]
		});

		var settingsPanel = Ext.create('Ext.Panel', {
			border : false,
			layout : 'vbox',
			title : 'Settings',
			width : '100%',
			collapsible: true,
			items : [ {
				xtype : 'checkbox',
				boxLabel : 'Zoom to last GPS location',
				checked : follow.last,
				id : 'followLast',
				margins : margins,
				listeners : {
					change : checkFollow
				}
			}, {
				xtype : 'checkbox',
				boxLabel : 'Zoom to scan locations',
				checked : follow.locations,
				id : 'followLocs',
				margins : margins,
				listeners : {
					change : checkFollow
				}
			}, {
				xtype : 'slider',
				fieldLabel : 'Heatmap radius',
				id : 'heatRadius',
				value : heatmap.get('radius'),
				minValue : 10,
				maxValue : 100,
				width : '100%',
				listeners : {
					changecomplete : slideRadius
				}
			} ]
		});

		var refreshPanel = Ext.create('Ext.Panel', {
			border : false,
			layout : 'vbox',
			title : 'Refresh',
			width : '100%',
			collapsible: true,
			items : [ {
				xtype : 'panel',
				layout : 'hbox',
				width : '100%',
				align : 'center',
				pack : 'center',
				items : [ {
					xtype : 'button',
					text : 'Play',
					id : 'play',
					disabled : true,
					margins : '5 5 5 5',
					listeners : {
						click : buttonPlay
					}
				}, {
					xtype : 'button',
					text : 'Pause',
					id : 'pause',
					margins : '5 5 5 5',
					listeners : {
						click : buttonPlay
					}
				}, {
					xtype : 'image',
					id : 'loading',
					src : '/busy.gif',
					margins : '5 5 5 5'
				} ]
			}, {
				xtype : 'slider',
				fieldLabel : 'Refresh',
				value : refresh / 1000,
				minValue : 1,
				maxValue : 100,
				width : '100%',
				listeners : {
					changecomplete : slideRefresh
				}
			} ]
		});

		var ctrlPanel = Ext.create('Ext.Panel', {
			layout : 'vbox',
			border : true,
			region : "east",
			width : 200,
			collapsible : true,
			autoScroll: true,
			items : [ layersPanel, infoPanel, settingsPanel, refreshPanel ]
		});

		Ext.create('Ext.Viewport', {
			layout : "fit",
			items : {
				layout : "border",
				deferredRender : false,
				items : [ mapPanel, ctrlPanel ]
			}
		});

		worker = new Worker("/get_gjson.js");
		worker.addEventListener('message', workerMessage, false);
		workerStart();
	}
});

function setupMap() {

	map = new OpenLayers.Map('map', {
		units : 'm',
		controls : [ new OpenLayers.Control.PanZoomBar(),
				new OpenLayers.Control.Navigation(),
				new OpenLayers.Control.ScaleLine(),
				new OpenLayers.Control.MousePosition() ]
	});
}

function setupLayers() {

	var layer = new OpenLayers.Layer.Google("Google Maps", {
		type : google.maps.MapTypeId.ROADMAP,
		numZoomLevels : 20,
	});
	layers.push(layer);

	var layer = new OpenLayers.Layer.Google("Google Satellite", {
		type : google.maps.MapTypeId.SATELLITE,
		numZoomLevels : 22
	});
	layers.push(layer);

	var layer = new OpenLayers.Layer.Google("Google Hybrid", {
		type : google.maps.MapTypeId.HYBRID,
		numZoomLevels : 20
	});
	layers.push(layer);

	var layer = new OpenLayers.Layer.Google("Google Terrain", {
		type : google.maps.MapTypeId.TERRAIN,
		numZoomLevels : 20
	});
	layers.push(layer);

	heatmap = new google.maps.visualization.HeatmapLayer();
	heatmap.set('radius', 30);
}

function updateLayers() {

	clearMarkers(markersLocation);
	for (var i = 0; i < points.length; i++) {
		var latLng = points[i];
		var marker = new google.maps.Marker({
			position : latLng,
		});
		markersLocation.push(marker);
	}

	clearMarkers(markersLast);
	if (typeof lastPoint != "undefined") {
		var icon = icon = "/crosshair.png";
		var marker = new google.maps.Marker({
			position : lastPoint,
			icon : icon,
		});
		markersLast.push(marker);
	}

	heatmap.setData(points);

	showLayers();
	zoom();
}

function updateInfo() {

	var dispLocs = Ext.getCmp('dispLocs');
	dispLocs.setValue(points.length);
	var dispCoords = Ext.getCmp('dispCoords');
	if (typeof lastPoint != "undefined")
		dispCoords.setValue(formatCoords(lastPoint));
	else
		dispCoords.setValue('');
}

function showLayers() {

	var baseMap = layers[0].mapObject;

	var locationsMap = overlay.locations ? baseMap : null;
	setMarkers(markersLocation, locationsMap);

	var lastMap = overlay.last ? baseMap : null;
	setMarkers(markersLast, lastMap);

	heatmap.setMap(overlay.heatmap ? baseMap : null);
}

function zoom() {

	var bounds = new OpenLayers.Bounds();
	var boundsUpdated = false;

	if (follow.locations)
		for (var i = 0; i < points.length; i++) {
			var latLng = points[i];
			bounds.extend(latLngToLonLat(latLng));
			boundsUpdated = true;
		}

	if (follow.last)
		if (typeof lastPoint != "undefined") {
			bounds.extend(latLngToLonLat(lastPoint));
			boundsUpdated = true;
		}

	if (boundsUpdated)
		map.zoomToExtent(bounds);
}

function checkOverlay(item, checked, opts) {

	var id = item.getId();

	switch (id) {
	case 'overlayLast':
		overlay.last = checked;
		break;
	case 'overlayLoc':
		overlay.locations = checked;
		break;
	case 'overlayHeat':
		overlay.heatmap = checked;
		Ext.getCmp('heatRadius').setDisabled(!checked);
		break;
	}

	showLayers();
}

function checkFollow(item, checked, opts) {

	var id = item.getId();

	switch (id) {
	case 'followLast':
		follow.last = checked;
		break;
	case 'followLocs':
		follow.locations = checked;
		break;
	}

	zoom();
}

function slideRadius(item, value, thumb) {

	heatmap.set('radius', value);
}

function slideRefresh(item, value, thumb) {

	refresh = value * 1000;
	workerSchedule();
}

function buttonPlay(item, e) {

	var id = item.getId();
	switch (id) {
	case 'play':
		isRefreshing = true;
		Ext.getCmp('play').setDisabled(true);
		Ext.getCmp('pause').setDisabled(false);
		break;
	case 'pause':
		isRefreshing = false;
		Ext.getCmp('pause').setDisabled(true);
		Ext.getCmp('play').setDisabled(false);
		break;
	}

	workerSchedule();
}

function workerStart() {

	Ext.getCmp('loading').show();
	worker.postMessage('');
}

function workerSchedule() {

	Ext.getCmp('loading').hide();
	clearTimeout(refreshTimeout);
	if (isRefreshing)
		refreshTimeout = setTimeout(workerStart, refresh);
}

function workerMessage(message) {

	if (message.data.length == 2) {
		points.length = 0;
		for (var i = 0; i < message.data[0].length; i++) {
			var coords = message.data[0][i];
			var latLng = new google.maps.LatLng(coords[0], coords[1])
			points.push(latLng);
		}

		if (typeof message.data[1] != "undefined")
			lastPoint = new google.maps.LatLng(message.data[1][0],
					message.data[1][1]);
		else
			lastPoint = undefined;

		updateLayers();
		updateInfo();
	}

	workerSchedule();
}

function latLngToLonLat(latLng) {

	var lonLat = new OpenLayers.LonLat(latLng.lng(), latLng.lat()).transform(
			projGps, projSm);

	return lonLat;
}

function clearMarkers(markers) {

	setMarkers(markers, null);
	markers.length = 0;
}

function setMarkers(markers, map) {

	for (var i = 0; i < markers.length; i++)
		markers[i].setMap(map);
}

function formatCoords(coords) {

	var formatted = coords.lat().toFixed(5) + '&deg<br/>'
			+ coords.lng().toFixed(5) + '&deg';
	return formatted;
}

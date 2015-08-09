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

self.addEventListener('message', getLocations);

function getLocations() {

	var xhr = new XMLHttpRequest();
	xhr.open('GET', '/gjson', true);
	xhr.onreadystatechange = function() {
		if (xhr.readyState == this.DONE)
			data = loadData(this.responseText);
	};
	xhr.ontimeout = function() {
		self.postMessage('');
	};
	xhr.onerror = function() {
		self.postMessage('');
	};
	xhr.send();
}

function loadData(results) {

	var points = [];
	var location;

	var features = JSON.parse(results).features;

	for (var i = 0; i < features.length; i++) {
		var coords = features[i].geometry.coordinates
		var properties = features[i].properties;
		if (typeof properties != "undefined" && properties.isLast)
			location = coords;
		else
			points.push(coords);
	}

	self.postMessage([ points, location ]);
}

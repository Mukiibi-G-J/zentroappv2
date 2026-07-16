/**
 * Resource admin - Dimension Value filtered by Dimension Code.
 * When Dimension Code changes, fetches Dimension Values for that dimension
 * and repopulates the Dimension Value Code dropdown.
 */
(function () {
    'use strict';

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    function initResourceDimensionFilter() {
        const dimensionCodeSelect = document.getElementById('id_dimension_code');
        const dimensionValueSelect = document.getElementById('id_dimension_value');

        if (!dimensionCodeSelect || !dimensionValueSelect) {
            return;
        }

        function getDimensionValuesUrl() {
            // Admin change form URL is e.g. /admin/resources/resource/123/change/
            // dimension-values is at model level: /admin/resources/resource/dimension-values/
            const path = window.location.pathname;
            const base = path.replace(/\/[^/]+\/change\/?$/, '');
            return base + 'dimension-values/';
        }

        function loadDimensionValues(dimensionCode) {
            dimensionValueSelect.innerHTML = '<option value="">---------</option>';
            if (!dimensionCode) {
                return;
            }

            const url = getDimensionValuesUrl() + '?dimension_code=' + encodeURIComponent(dimensionCode);
            const csrftoken = getCookie('csrftoken');

            fetch(url, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrftoken
                },
                credentials: 'same-origin'
            })
                .then(function (response) {
                    return response.json();
                })
                .then(function (data) {
                    const values = data.values || [];
                    values.forEach(function (item) {
                        const opt = document.createElement('option');
                        opt.value = item.code;
                        opt.textContent = item.code + (item.description ? ' — ' + item.description : '');
                        dimensionValueSelect.appendChild(opt);
                    });
                })
                .catch(function () {
                    dimensionValueSelect.innerHTML = '<option value="">---------</option>';
                });
        }

        dimensionCodeSelect.addEventListener('change', function () {
            dimensionValueSelect.innerHTML = '<option value="">---------</option>';
            const dimensionCode = dimensionCodeSelect.value;
            if (dimensionCode) {
                loadDimensionValues(dimensionCode);
            }
        });

        // When user changes Dimension Code, options are loaded. On initial load
        // the server already renders the correct Dimension Value options.
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initResourceDimensionFilter);
    } else {
        initResourceDimensionFilter();
    }
})();

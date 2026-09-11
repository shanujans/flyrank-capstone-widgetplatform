/*
 * FlyRank embeddable widget bundle — v1
 *
 * This is the ENTIRE payload a customer's browser downloads (and caches for
 * a year, per the Cache-Control header the server sends alongside it).
 * Everything else — which widget to render, its fields, where to submit —
 * is fetched at runtime from the ?id= on this very <script> tag, so the
 * embed snippet stays a single line no matter how the widget is configured.
 */
(function () {
  "use strict";

  function getScriptEl() {
    // document.currentScript is reliable for a synchronously-executing
    // classic script; async/defer scripts still get it in modern browsers.
    if (document.currentScript) return document.currentScript;
    var scripts = document.getElementsByTagName("script");
    for (var i = scripts.length - 1; i >= 0; i--) {
      if (scripts[i].src && scripts[i].src.indexOf("/widget/") !== -1) return scripts[i];
    }
    return null;
  }

  var scriptEl = getScriptEl();
  if (!scriptEl) {
    console.error("[flyrank-widget] could not locate its own <script> tag");
    return;
  }

  var scriptUrl = new URL(scriptEl.src);
  var widgetId = scriptUrl.searchParams.get("id");
  var apiBase = scriptUrl.origin; // the API lives on the same origin the bundle was fetched from

  if (!widgetId) {
    console.error("[flyrank-widget] missing ?id= on the embed snippet");
    return;
  }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "style") node.style.cssText = attrs[k];
      else node.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) {
      node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return node;
  }

  function inputTypeFor(fieldType) {
    if (fieldType === "email") return "email";
    if (fieldType === "tel") return "tel";
    if (fieldType === "checkbox") return "checkbox";
    return "text";
  }

  function renderWidget(config) {
    var container = el("div", {
      style:
        "max-width:360px;border:1px solid #ddd;border-radius:10px;padding:16px;" +
        "font-family:system-ui,-apple-system,sans-serif;box-shadow:0 2px 10px rgba(0,0,0,.08);",
      "data-flyrank-widget-id": widgetId,
    });

    container.appendChild(el("h3", { style: "margin:0 0 6px;font-size:16px;" }, [config.title]));
    if (config.description) {
      container.appendChild(
        el("p", { style: "margin:0 0 12px;font-size:13px;color:#555;" }, [config.description])
      );
    }

    var form = el("form", { style: "display:flex;flex-direction:column;gap:8px;" });
    var inputsByName = {};

    (config.fields || []).forEach(function (field) {
      var wrapper = el("label", { style: "font-size:13px;color:#333;display:flex;flex-direction:column;gap:4px;" });
      wrapper.appendChild(document.createTextNode(field.label + (field.required ? " *" : "")));

      var input =
        field.type === "textarea"
          ? el("textarea", { rows: "3", name: field.name, style: "padding:6px 8px;border:1px solid #ccc;border-radius:6px;" })
          : el("input", {
              type: inputTypeFor(field.type),
              name: field.name,
              style: "padding:6px 8px;border:1px solid #ccc;border-radius:6px;",
            });

      if (field.required) input.setAttribute("required", "required");
      inputsByName[field.name] = input;
      wrapper.appendChild(input);
      form.appendChild(wrapper);
    });

    // Honeypot: visually hidden (not display:none, which some bots skip
    // filling on purpose) and off the tab order, so real visitors never
    // interact with it but naive bots filling every field still do.
    var honeypot = el("input", {
      type: "text",
      name: "hp_field",
      tabindex: "-1",
      autocomplete: "off",
      style: "position:absolute;left:-9999px;width:1px;height:1px;opacity:0;",
      "aria-hidden": "true",
    });
    form.appendChild(honeypot);

    var statusEl = el("div", { style: "font-size:13px;min-height:16px;" });
    var submitBtn = el(
      "button",
      { type: "submit", style: "margin-top:4px;padding:8px 12px;border:0;border-radius:6px;background:#111;color:#fff;cursor:pointer;" },
      [config.button_text || "Submit"]
    );

    form.appendChild(submitBtn);
    form.appendChild(statusEl);

    form.addEventListener("submit", function (evt) {
      evt.preventDefault();
      submitBtn.disabled = true;
      statusEl.style.color = "#555";
      statusEl.textContent = "Sending...";

      var data = {};
      Object.keys(inputsByName).forEach(function (name) {
        data[name] = inputsByName[name].value;
      });

      fetch(apiBase + "/public/widgets/" + encodeURIComponent(widgetId) + "/submissions", {
        method: "POST",
        mode: "cors",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data: data, hp_field: honeypot.value }),
      })
        .then(function (res) {
          return res.json().then(function (body) {
            return { ok: res.ok, status: res.status, body: body };
          });
        })
        .then(function (result) {
          submitBtn.disabled = false;
          if (result.ok) {
            statusEl.style.color = "#0a7a2f";
            statusEl.textContent = "Thanks! Your submission was received.";
            form.reset();
          } else {
            statusEl.style.color = "#b00020";
            var detail = result.body && result.body.detail;
            statusEl.textContent = Array.isArray(detail) ? detail.join(", ") : detail || "Something went wrong.";
          }
        })
        .catch(function (err) {
          submitBtn.disabled = false;
          statusEl.style.color = "#b00020";
          statusEl.textContent = "Network error — please try again.";
          console.error("[flyrank-widget] submission failed", err);
        });
    });

    container.appendChild(form);

    // Mount right after the <script> tag itself, so placement in the page
    // matches wherever the customer pasted the embed snippet.
    scriptEl.parentNode.insertBefore(container, scriptEl.nextSibling);
  }

  fetch(apiBase + "/public/widgets/" + encodeURIComponent(widgetId) + "/config", { mode: "cors" })
    .then(function (res) {
      if (!res.ok) throw new Error("config fetch failed: " + res.status);
      return res.json();
    })
    .then(renderWidget)
    .catch(function (err) {
      console.error("[flyrank-widget] failed to load widget config", err);
    });
})();

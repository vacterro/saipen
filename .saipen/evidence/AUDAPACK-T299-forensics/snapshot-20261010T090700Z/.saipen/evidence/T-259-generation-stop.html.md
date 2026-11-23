# T-259 live generation-control capture (chatgpt.com, 2026-09-29)

Captured in the AUDAPACK dedicated Chromium profile while a real turn was
generating. Structure only: no conversation text, prompt, account data or
token appears here. The IDLE sample is the composer before the prompt was
sent; the t+2s sample is the live generation moment.

```text
=== IDLE (before send) ===
{
  "t": 1790699813141,
  "composer_form": {
    "tag": "form",
    "type": "",
    "role": "",
    "id": "",
    "data_testid": "",
    "aria_label": "",
    "title": "",
    "disabled": false,
    "aria_disabled": "",
    "hidden": false,
    "aria_hidden": "",
    "class": "relative flex flex-col gap-2",
    "rect": [
      16,
      341,
      597,
      87
    ],
    "display": "flex",
    "visibility": "visible",
    "pointer_events": "auto"
  },
  "stopish": [],
  "slot_controls": [
    {
      "tag": "button",
      "type": "button",
      "role": "",
      "id": "",
      "data_testid": "",
      "aria_label": "Add files and more",
      "title": "",
      "disabled": false,
      "aria_disabled": "",
      "hidden": false,
      "aria_hidden": "",
      "class": "no-drag cursor-interaction items-center select-none disabled:cursor-default aria-disabled:",
      "rect": [
        24,
        384,
        36,
        36
      ],
      "display": "flex",
      "visibility": "visible",
      "pointer_events": "auto"
    },
    {
      "tag": "button",
      "type": "button",
      "role": "",
      "id": "radix-_r_11_",
      "data_testid": "",
      "aria_label": "Select ChatGPT model",
      "title": "",
      "disabled": false,
      "aria_disabled": "",
      "hidden": false,
      "aria_hidden": "",
      "class": "no-drag cursor-interaction items-center select-none disabled:cursor-default aria-disabled:",
      "rect": [
        438,
        384,
        87,
        36
      ],
      "display": "flex",
      "visibility": "visible",
      "pointer_events": "auto"
    },
    {
      "tag": "button",
      "type": "button",
      "role": "",
      "id": "",
      "data_testid": "",
      "aria_label": "Dictate",
      "title": "",
      "disabled": false,
      "aria_disabled": "",
      "hidden": false,
      "aria_hidden": "",
      "class": "no-drag cursor-interaction items-center select-none disabled:cursor-default aria-disabled:",
      "rect": [
        525,
        384,
        36,
        36
      ],
      "display": "flex",
      "visibility": "visible",
      "pointer_events": "auto"
    },
    {
      "tag": "button",
      "type": "button",
      "role": "",
      "id": "",
      "data_testid": "",
      "aria_label": "Start Voice",
      "title": "",
      "disabled": false,
      "aria_disabled": "",
      "hidden": false,
      "aria_hidden": "",
      "class": "cursor-interaction size-token-button-composer flex items-center justify-center rounded-ful",
      "rect": [
        569,
        384,
        36,
        36
      ],
      "display": "flex",
      "visibility": "visible",
      "pointer_events": "auto"
    }
  ],
  "latest_assistant_has_final_actions": false
}
--- t+2s stopish=1 slot=4 final=False ---
   STOPISH {"tag": "button", "type": "button", "data_testid": "", "aria_label": "Stop", "id": "", "in_composer_form": true, "in_turn": false, "in_response_actions": false, "rect": [579, 384, 36, 36]}
{
  "t": 1790699818707,
  "composer_form": {
    "tag": "form",
    "type": "",
    "role": "",
    "id": "",
    "data_testid": "",
    "aria_label": "",
    "title": "",
    "disabled": false,
    "aria_disabled": "",
    "hidden": false,
    "aria_hidden": "",
    "class": "relative flex flex-col gap-2",
    "rect": [
      16,
      341,
      607,
      87
    ],
    "display": "flex",
    "visibility": "visible",
    "pointer_events": "auto"
  },
  "stopish": [
    {
      "tag": "button",
      "type": "button",
      "role": "",
      "id": "",
      "data_testid": "",
      "aria_label": "Stop",
      "title": "",
      "disabled": false,
      "aria_disabled": "",
      "hidden": false,
      "aria_hidden": "",
      "class": "cursor-interaction size-token-button-composer flex items-center justify-center rounded-ful",
      "rect": [
        579,
        384,
        36,
        36
      ],
      "display": "flex",
      "visibility": "visible",
      "pointer_events": "auto",
      "in_composer_form": true,
      "in_turn": false,
      "in_response_actions": false,
      "ancestor_chain": [
        {
          "depth": 0,
          "tag": "button",
          "id": "",
          "data_testid": "",
          "aria_label": "Stop",
          "class": "cursor-interaction size-token-button-composer flex items-cen"
        },
        {
          "depth": 1,
          "tag": "div",
          "id": "",
          "data_testid": "",
          "aria_label": "",
          "class": "flex items-center"
        },
        {
          "depth": 2,
          "tag": "div",
          "id": "",
          "data_testid": "",
          "aria_label": "",
          "class": "flex shrink-0 items-center gap-2"
        },
        {
          "depth": 3,
          "tag": "div",
          "id": "",
          "data_testid": "",
          "aria_label": "",
          "class": "flex min-w-0 items-center justify-end shrink-0"
        },
        {
          "depth": 4,
          "tag": "div",
          "id": "",
          "data_testid": "",
          "aria_label": "",
          "class": "min-w-0 max-sm:col-start-3 max-sm:row-start-2"
        },
        {
          "depth": 5,
          "tag": "div",
          "id": "",
          "data_testid": "",
          "aria_label": "",
          "class": "ComposerLayoutFooter-_8IVRO"
        }
      ],
      "children": [
        {
          "tag": "svg",
          "type": "",
          "role": "",
          "id": "",
          "data_testid": "",
          "aria_label": "",
          "title": "",
          "disabled": false,
          "aria_disabled": "",
          "hidden": false,
          "aria_hidden": "",
          "class": "icon-primary-action text-composer-primary",
          "rect": [
            587,
            392,
            20,
            20
          ],
          "display": "block",
          "visibility": "visible",
          "pointer_events": "auto"
        }
      ]
    }
  ],
  "slot_controls": [
    {
      "tag": "button",
      "type": "button",
      "role": "",
      "id": "",
      "data_testid": "",
      "aria_label": "Add files and more",
      "title": "",
      "disabled": false,
      "aria_disabled": "",
      "hidden": false,
      "aria_hidden": "",
      "class": "no-drag cursor-interaction items-center select-none disabled:cursor-default aria-disabled:",
      "rect": [
        24,
        384,
        36,
        36
      ],
      "display": "flex",
      "visibility": "visible",
      "pointer_events": "auto"
    },
    {
      "tag": "button",
      "type": "button",
      "role": "",
      "id": "radix-_r_b7_",
      "data_testid": "",
      "aria_label": "Select ChatGPT model",
      "title": "",
      "disabled": false,
      "aria_disabled": "",
      "hidden": false,
      "aria_hidden": "",
      "class": "no-drag cursor-interaction items-center select-none disabled:cursor-default aria-disabled:",
      "rect": [
        448,
        384,
        87,
        36
      ],
      "display": "flex",
      "visibility": "visible",
      "pointer_events": "auto"
    },
    {
      "tag": "button",
      "type": "button",
      "role": "",
      "id": "",
      "data_testid": "",
      "aria_label": "Dictate",
      "title": "",
      "disabled": true,
      "aria_disabled": "",
      "hidden": false,
      "aria_hidden": "",
      "class": "no-drag cursor-interaction items-center select-none disabled:cursor-default aria-disabled:",
      "rect": [
        535,
        384,
        36,
        36
      ],
      "display": "flex",
      "visibility": "visible",
      "pointer_events": "auto"
    },
    {
      "tag": "button",
      "type": "button",
      "role": "",
      "id": "",
      "data_testid": "",
      "aria_label": "Stop",
      "title": "",
      "disabled": false,
      "aria_disabled": "",
      "hidden": false,
      "aria_hidden": "",
      "class": "cursor-interaction size-token-button-composer flex items-center justify-center rounded-ful",
      "rect": [
        579,
        384,
        36,
        36
      ],
      "display": "flex",
      "visibility": "visible",
      "pointer_events": "auto"
    }
  ],
  "latest_assistant_has_final_actions": false
}
--- t+4s stopish=0 slot=3 final=False ---
--- t+6s stopish=0 slot=4 final=False ---
--- t+8s stopish=0 slot=4 final=False ---
--- t+10s stopish=0 slot=4 final=False ---
--- t+12s stopish=0 slot=4 final=False ---
--- t+14s stopish=0 slot=4 final=False ---
--- t+16s stopish=0 slot=4 final=False ---
--- t+18s stopish=0 slot=4 final=False ---
--- t+20s stopish=0 slot=4 final=False ---
--- t+22s stopish=0 slot=4 final=False ---
--- t+24s stopish=0 slot=4 final=False ---
--- t+26s stopish=0 slot=4 final=False ---
--- t+28s stopish=0 slot=4 final=False ---
--- t+30s stopish=0 slot=4 final=False ---
--- t+32s stopish=0 slot=4 final=False ---
--- t+34s stopish=0 slot=4 final=False ---
--- t+36s stopish=0 slot=4 final=False ---
--- t+38s stopish=0 slot=4 final=False ---
--- t+40s stopish=0 slot=4 final=False ---
--- t+42s stopish=0 slot=4 final=False ---
--- t+44s stopish=0 slot=4 final=False ---
--- t+46s stopish=0 slot=4 final=False ---
--- t+48s stopish=0 slot=4 final=False ---
--- t+50s stopish=0 slot=4 final=False ---
--- t+52s stopish=0 slot=4 final=False ---
--- t+54s stopish=0 slot=4 final=False ---
--- t+56s stopish=0 slot=4 final=False ---
--- t+58s stopish=0 slot=4 final=False ---
--- t+60s stopish=0 slot=4 final=False ---
--- t+62s stopish=0 slot=4 final=False ---
--- t+64s stopish=0 slot=4 final=False ---
--- t+66s stopish=0 slot=4 final=False ---
--- t+68s stopish=0 slot=4 final=False ---
--- t+70s stopish=0 slot=4 final=False ---
--- t+72s stopish=0 slot=4 final=False ---
--- t+74s stopish=0 slot=4 final=False ---
--- t+76s stopish=0 slot=4 final=False ---
--- t+78s stopish=0 slot=4 final=False ---
--- t+80s stopish=0 slot=4 final=False ---
--- t+82s stopish=0 slot=4 final=False ---
--- t+84s stopish=0 slot=4 final=False ---
--- t+86s stopish=0 slot=4 final=False ---
--- t+88s stopish=0 slot=4 final=False ---
--- t+90s stopish=0 slot=4 final=False ---
--- t+92s stopish=0 slot=4 final=False ---
--- t+94s stopish=0 slot=4 final=False ---
--- t+96s stopish=0 slot=4 final=False ---
--- t+98s stopish=0 slot=4 final=False ---
--- t+100s stopish=0 slot=4 final=False ---
--- t+102s stopish=0 slot=4 final=False ---
--- t+104s stopish=0 slot=4 final=False ---
--- t+106s stopish=0 slot=4 final=False ---
--- t+108s stopish=0 slot=4 final=False ---
--- t+110s stopish=0 slot=4 final=False ---
--- t+112s stopish=0 slot=4 final=False ---
--- t+114s stopish=0 slot=4 final=False ---
--- t+116s stopish=0 slot=4 final=False ---
--- t+118s stopish=0 slot=4 final=False ---
--- t+120s stopish=0 slot=4 final=False ---
--- t+122s stopish=0 slot=4 final=False ---
--- t+124s stopish=0 slot=4 final=False ---
--- t+126s stopish=0 slot=4 final=False ---
--- t+128s stopish=0 slot=4 final=False ---
--- t+130s stopish=0 slot=4 final=False ---
--- t+132s stopish=0 slot=4 final=False ---
--- t+134s stopish=0 slot=4 final=False ---
--- t+136s stopish=0 slot=4 final=False ---
--- t+138s stopish=0 slot=4 final=False ---
--- t+140s stopish=0 slot=4 final=False ---
--- t+142s stopish=0 slot=4 final=False ---
--- t+144s stopish=0 slot=4 final=False ---
--- t+146s stopish=0 slot=4 final=False ---
--- t+148s stopish=0 slot=4 final=False ---
```

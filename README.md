# textboxer
A python script/lib for making custom textboxes that look like they are from games.

## Requirements
Python 3.10  
Pillow

Image and font files from the appropriate game are *required* for it to work, and are not included in this repository.  
Each game "style" also requires some metadata files specifying the layout, example ones for [OMORI](resources/styles/omori/data) and [Oneshot](resources/styles/oneshot/data) are included.  
(Example/reference style coming soon™)

## Invoking
Textboxes can be created by either using `generate()`, which gives the most flexibility, or `parsestr()`, which is less flexible but more appropriate for something like a Discord bot.  
(`parsestrlist()` can also be used, but will probably be removed later, since you can use the `presplit` kwarg of `parsestr()` for the same sort of thing)

The syntax for `parsestr()` is defined in the `str` key in the `parse.json` of the style.

`gen_help()` can be called to create a help message that is accurate to the currently available styles, including `parsestr()` syntax and recognized flags.

## Examples
`generate("oneshot", {"main": "My rams clock at 1333 megaherds."}, {"face": "shepherd"})`  
or `parsestr("oneshot shepherd My rams clock at 1333 megaherds.")`

![tmpg8ljys17](https://user-images.githubusercontent.com/66188216/156435804-e1d1d78c-dc63-4048-bfa2-29d609ca69d0.PNG)

![Screenshot from 2020-06-21 19-39-47](https://user-images.githubusercontent.com/66188216/156435960-1001f002-075e-44e1-a86e-aed1a843cb03.png)


`generate("omori", {"main": "Hi, OMORI! Cliff-faced as usual, I see.\nYou should totally smile more! I've always liked your smile.", "name": "MARI"}, {"face": "mari_dw_smile2"})`  
or `parsestr("omori MARI mari_dw_smile2 Hi, OMORI! Cliff-faced as usual, I see.\nYou should totally smile more! I've always liked your smile.")`

![tmpvga6r7hj](https://user-images.githubusercontent.com/66188216/156437165-4b04d18b-add3-44e8-bd5a-75abc6aa24b7.PNG)

![image](https://user-images.githubusercontent.com/66188216/156436883-afa277a0-f114-41bb-953d-2f3944c33b7e.png)

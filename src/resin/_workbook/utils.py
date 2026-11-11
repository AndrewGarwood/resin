"""
*`@file`* `_workbook/utils`
"""



def is_excel_error_value(value: object, /) -> bool:
    return (
        not isinstance(value, bool) # isinstance(True, int) → True
        and isinstance(value, int) 
        and -2146827000 < value < -2146826000
    )



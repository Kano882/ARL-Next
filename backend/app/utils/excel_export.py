"""外部资产文本只作为单元格文字保存，数值保留原有类型。"""
from openpyxl.cell import WriteOnlyCell


def append_literal_row(worksheet, values):
    cells = []
    for value in values:
        cell = WriteOnlyCell(worksheet, value=value)
        if isinstance(value, str):
            cell.data_type = 's'
        cells.append(cell)
    worksheet.append(cells)


def set_literal_cell(worksheet, row, column, value):
    cell = worksheet.cell(row=row, column=column, value=value)
    if isinstance(value, str):
        cell.data_type = 's'
    return cell

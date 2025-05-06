import os
import re
import json

# Функция для поиска плагинов в каталоге plugins/
def find_plugins(root_dir):
    plugins = []
    for dirpath, _, filenames in os.walk(root_dir):
        if 'index.js' in filenames or 'index.ts' in filenames:
            plugins.append(dirpath)
    return plugins

# Функция для извлечения имени класса из файла index.js или index.ts
def extract_plugin_name(plugin_dir):
    index_file = os.path.join(plugin_dir, 'index.js')
    if not os.path.exists(index_file):
        index_file = os.path.join(plugin_dir, 'index.ts')
    with open(index_file, 'r') as f:
        content = f.read()
        match = re.search(r'export default class (\w+)', content)
        if match:
            return match.group(1)
    return None

# Генерация строки импорта
def generate_import_statement(plugin_name, package_name):
    return f"import {plugin_name} from '{package_name}';"

# Генерация строки регистрации
def generate_registration_statement(plugin_name, key):
    return f"new {plugin_name}().configure({{ key: '{key}' }}),"

# Проверка наличия строки в файле
def is_line_in_file(file_path, line):
    with open(file_path, 'r') as f:
        content = f.read()
        return line in content

# Обновление MainPreset.js с проверкой на дублирование
def update_main_preset(plugins_data):
    main_preset_path = 'superset/superset-frontend/src/visualizations/presets/MainPreset.js'
    with open(main_preset_path, 'r') as f:
        content = f.read()
    
    updated = False
    for plugin_name, package_name, key in plugins_data:
        import_line = generate_import_statement(plugin_name, package_name)
        registration_line = generate_registration_statement(plugin_name, key)
        
        if not is_line_in_file(main_preset_path, import_line):
            content = import_line + '\n' + content
            print(f"Добавлен импорт для {plugin_name}")
            updated = True
        else:
            print(f"Импорт для {plugin_name} уже существует, пропускаем")
        
        if not is_line_in_file(main_preset_path, registration_line):
            content += f"\n// Регистрация плагина {plugin_name}\n{registration_line}"
            print(f"Добавлена регистрация для {plugin_name}")
            updated = True
        else:
            print(f"Регистрация для {plugin_name} уже существует, пропускаем")
    
    if updated:
        with open(main_preset_path, 'w') as f:
            f.write(content)

# Обновление package.json с проверкой на дублирование
def update_package_json(plugins_data):
    package_json_path = 'superset/superset-frontend/package.json'
    with open(package_json_path, 'r') as f:
        data = json.load(f)
    
    if 'dependencies' not in data:
        data['dependencies'] = {}
    
    updated = False
    for _, package_name, _ in plugins_data:
        plugin_dir = package_name.split('/')[-1]
        dependency_path = f"file:./plugins/{plugin_dir}"
        if package_name not in data['dependencies']:
            data['dependencies'][package_name] = dependency_path
            print(f"Добавлена зависимость для {package_name}")
            updated = True
        else:
            print(f"Зависимость для {package_name} уже существует, пропускаем")
    
    if updated:
        with open(package_json_path, 'w') as f:
            json.dump(data, f, indent=2)

# Основной процесс
if __name__ == '__main__':
    plugins_dir = 'plugins'
    plugins = find_plugins(plugins_dir)
    plugins_data = []
    
    for plugin in plugins:
        plugin_name = extract_plugin_name(plugin)
        if plugin_name:
            plugin_dir = plugin.split('/')[-1]
            package_name = f"@superset-ui/{plugin_dir}"
            key = plugin_dir.replace('superset-plugin-chart-', '')
            plugins_data.append((plugin_name, package_name, key))
    
    update_main_preset(plugins_data)
    update_package_json(plugins_data)

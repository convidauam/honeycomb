"""
Tests para las vistas CRUD
"""

import unittest
from pyramid import testing
from honeycomb.models import CellText, CellAnimation, CellRichText, CellWebContent, CellIcon, Honeycomb, BeeHive


class CRUDTests(unittest.TestCase):
    
    def setUp(self):
        self.config = testing.setUp()
        self.beehive = BeeHive()
        self.honeycomb = Honeycomb('test_hc', 'Test Honeycomb')
        self.honeycomb.__parent__ = self.beehive
        self.beehive['test_hc'] = self.honeycomb
    
    def tearDown(self):
        testing.tearDown()
    
    def test_create_cell_text(self):
        """Prueba creación de CellText"""
        cell = CellText(
            name='test_text',
            contents='Test content',
            title='Test Title',
            icon='http://example.com/icon.png'
        )
        
        self.honeycomb['test_text'] = cell
        self.beehive.add_node(cell)
        
        # Verificar que la celda se creó correctamente
        self.assertEqual(cell.title, 'Test Title')
        self.assertEqual(cell.contents, 'Test content')
        self.assertIn('test_text', self.honeycomb)
    
    def test_update_cell_text(self):
        """Prueba actualización de CellText"""
        cell = CellText(
            name='test_text',
            contents='Initial content',
            title='Initial Title'
        )
        
        self.honeycomb['test_text'] = cell
        
        # Actualizar
        cell.title = 'Updated Title'
        cell.contents = 'Updated content'
        
        self.assertEqual(cell.title, 'Updated Title')
        self.assertEqual(cell.contents, 'Updated content')
    
    def test_delete_cell_text(self):
        """Prueba eliminación de CellText"""
        cell = CellText(
            name='test_text',
            contents='Test content',
            title='Test Title'
        )
        
        self.honeycomb['test_text'] = cell
        self.beehive.add_node(cell)
        
        # Verificar que existe
        self.assertIn('test_text', self.honeycomb)
        
        # Eliminar
        del self.honeycomb['test_text']
        self.beehive.remove_node(str(cell.id))
        
        # Verificar que fue eliminada
        self.assertNotIn('test_text', self.honeycomb)
    
    def test_create_cell_richtext(self):
        """Prueba creación de CellRichText"""
        cell = CellRichText(
            name='test_richtext',
            contents='<p>HTML Content</p>',
            title='Rich Title'
        )
        
        self.honeycomb['test_richtext'] = cell
        self.beehive.add_node(cell)
        
        self.assertEqual(cell.title, 'Rich Title')
        self.assertEqual(cell.source, '<p>HTML Content</p>')
    
    def test_create_cell_animation(self):
        """Prueba creación de CellAnimation"""
        cell = CellAnimation(
            name='test_animation',
            url='http://example.com/animation.mp4',
            title='Animation Title'
        )
        
        self.honeycomb['test_animation'] = cell
        self.beehive.add_node(cell)
        
        self.assertEqual(cell.title, 'Animation Title')
        self.assertEqual(cell.href, 'http://example.com/animation.mp4')
    
    def test_create_cell_webcontent(self):
        """Prueba creación de CellWebContent"""
        cell = CellWebContent(
            name='test_webcontent',
            url='http://example.com/content',
            title='Web Content Title'
        )
        
        self.honeycomb['test_webcontent'] = cell
        self.beehive.add_node(cell)
        
        self.assertEqual(cell.title, 'Web Content Title')
        self.assertEqual(cell.href, 'http://example.com/content')
    
    def test_create_cell_icon(self):
        """Prueba creación de CellIcon"""
        cell = CellIcon(
            name='test_icon',
            title='Icon Title',
            icon='http://example.com/icon.png'
        )
        
        self.honeycomb['test_icon'] = cell
        self.beehive.add_node(cell)
        
        self.assertEqual(cell.title, 'Icon Title')
        self.assertEqual(cell.icon, 'http://example.com/icon.png')
    
    def test_parent_id_support(self):
        """Prueba que parent_id permite crear celdas anidadas"""
        # Crear un nodo padre
        from honeycomb.models import CellNode
        parent_node = CellNode(name='parent', title='Parent Node')
        parent_node.__parent__ = self.honeycomb
        self.honeycomb['parent'] = parent_node
        
        # Crear una celda dentro del nodo padre
        cell = CellText(
            name='nested_text',
            contents='Nested content',
            title='Nested Title'
        )
        
        parent_node['nested_text'] = cell
        cell.__parent__ = parent_node
        
        # Verificar que la celda está dentro del nodo padre
        self.assertIn('nested_text', parent_node)
        self.assertEqual(cell.__parent__, parent_node)


if __name__ == '__main__':
    unittest.main()

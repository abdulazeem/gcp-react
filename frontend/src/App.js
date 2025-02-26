import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = "http://localhost:8000";

function App() {
  const [todos, setTodos] = useState([]);
  const [newTodo, setNewTodo] = useState({ title: '', description: '' });

  useEffect(() => {
    fetchTodos();
  }, []);

  const fetchTodos = async () => {
    try {
      const response = await axios.get(`${API_URL}/todos/`);
      setTodos(response.data);
    } catch (error) {
      console.error("Error fetching todos:", error);
    }
  };

  const createTodo = async () => {
    if (!newTodo.title.trim()) return;
    try {
      await axios.post(`${API_URL}/todos/`, newTodo);
      setNewTodo({ title: '', description: '' });
      await fetchTodos();
    } catch (error) {
      console.error("Error creating todo:", error);
    }
  };

  const deleteTodo = async (id) => {
    try {
      await axios.delete(`${API_URL}/todos/${id}`);
      await fetchTodos();
    } catch (error) {
      console.error("Error deleting todo:", error);
    }
  };

  return (
    <div style={{ padding: '20px', maxWidth: '800px', margin: '0 auto' }}>
      <h1>Todo List</h1>
      <div style={{ marginBottom: '20px' }}>
        <input
          style={{ marginRight: '10px', padding: '5px' }}
          placeholder="Title"
          value={newTodo.title}
          onChange={(e) => setNewTodo({...newTodo, title: e.target.value})}
        />
        <input
          style={{ marginRight: '10px', padding: '5px' }}
          placeholder="Description"
          value={newTodo.description}
          onChange={(e) => setNewTodo({...newTodo, description: e.target.value})}
        />
        <button
          style={{ padding: '5px 15px' }}
          onClick={createTodo}
        >
          Add Todo
        </button>
      </div>

      <div>
        {todos.map(todo => (
          <div
            key={todo.id}
            style={{
              border: '1px solid #ddd',
              padding: '10px',
              marginBottom: '10px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}
          >
            <div>
              <h3 style={{ margin: '0 0 5px 0' }}>{todo.title}</h3>
              <p style={{ margin: '0', color: '#666' }}>{todo.description}</p>
            </div>
            <button
              style={{
                padding: '5px 10px',
                backgroundColor: '#ff4444',
                color: 'white',
                border: 'none',
                cursor: 'pointer'
              }}
              onClick={() => deleteTodo(todo.id)}
            >
              Delete
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export default App;
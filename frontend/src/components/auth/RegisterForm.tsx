import React, { useState, useEffect } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface RegistrationFormData {
  fullName: string;
  email: string;
  username: string;
  password: string;
  confirmPassword: string;
  dni: string;
  phoneNumber: string;
  age: number;
  gender: string;
  weight: number;
  height: number;
  zone: string;
  occupation: string;
}

interface FormErrors {
  [key: string]: string;
}

interface RegisterFormProps {
  onRegisterSuccess?: () => void;
}

export const RegisterForm: React.FC<RegisterFormProps> = ({ onRegisterSuccess }) => {
  const navigate = useNavigate();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const [formData, setFormData] = useState<RegistrationFormData>({
    fullName: '',
    email: '',
    username: '',
    password: '',
    confirmPassword: '',
    dni: '',
    phoneNumber: '',
    age: 0,
    gender: '',
    weight: 0,
    height: 0,
    zone: '',
    occupation: ''
  });

  const [errors, setErrors] = useState<FormErrors>({});
  const [touched, setTouched] = useState<{ [key: string]: boolean }>({});
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState<boolean>(false);

  // URL del API - Se configura automáticamente según el entorno
  const API_BASE_URL = process.env.NODE_ENV === 'production' 
    ? process.env.REACT_APP_API_URL || 'https://*.com'
    : process.env.REACT_APP_API_URL || 'http://localhost:8000';

  const occupationOptions = [
    "Sin nivel educativo/sin instrucción",
    "Preescolar",
    "Primaria incompleta",
    "Primaria completa",
    "Secundaria incompleta",
    "Secundaria completa",
    "Técnica superior incompleta",
    "Técnica superior completa",
    "Universitaria incompleta",
    "Universitaria completa",
    "Maestría/doctorado"
  ];

  useEffect(() => {
    let timeoutId: NodeJS.Timeout;
    
    if (successMessage) {
      timeoutId = setTimeout(() => {
        if (onRegisterSuccess) {
          onRegisterSuccess();
        } else {
          navigate('/login');
        }
      }, 2000);
    }
  
    return () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [successMessage, navigate, onRegisterSuccess]);

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    const { key, currentTarget } = e;
    const name = currentTarget.name;
    
    if (name === 'fullName') {
      if (/[0-9]/.test(key)) {
        e.preventDefault();
      }
    }
    
    if (name === 'dni' || name === 'phoneNumber' || name === 'height') {
      if (!/[0-9]/.test(key) && key !== 'Backspace' && key !== 'Delete' && key !== 'ArrowLeft' && key !== 'ArrowRight' && key !== 'Tab') {
        e.preventDefault();
      }
    }
  };

  const validateField = (name: string, value: string | number): string => {
    switch (name) {
      case 'fullName':
        if (!value) return 'El nombre completo es requerido';
        if (value.toString().length < 2) return 'El nombre completo debe tener al menos 2 caracteres';
        if (!/^[A-Za-zÁáÉéÍíÓóÚúÑñ ]+$/.test(value.toString())) {
          return 'El nombre completo solo puede contener letras y espacios';
        }
        break;
      case 'email':
        if (!value) return 'El correo electrónico es requerido';
        if (!/^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i.test(value.toString())) {
          return 'Ingrese un correo electrónico válido';
        }
        break;
      case 'username':
        if (!value) return 'El usuario es requerido';
        if (!/(?=.*[A-Z])(?=.*[a-z])(?=.*\d)[A-Za-z\d]{6,20}$/.test(value.toString())) {
          return 'El usuario debe tener entre 6 y 20 caracteres, al menos una mayúscula, una minúscula y un número';
        }
        break;
      case 'password':
        if (!value) return 'La contraseña es requerida';
        if (value.toString().length < 8) {
          return 'La contraseña debe tener al menos 8 caracteres';
        }
        if (!/(?=.*[a-z])/.test(value.toString())) {
          return 'La contraseña debe contener al menos una letra minúscula';
        }
        if (!/(?=.*[A-Z])/.test(value.toString())) {
          return 'La contraseña debe contener al menos una letra mayúscula';
        }
        if (!/(?=.*\d)/.test(value.toString())) {
          return 'La contraseña debe contener al menos un número';
        }
        if (!/(?=.*[@$!%*?&])/.test(value.toString())) {
          return 'La contraseña debe contener al menos un carácter especial (@$!%*?&)';
        }
        break;
      case 'confirmPassword':
        if (!value) return 'Debe confirmar la contraseña';
        if (value !== formData.password) {
          return 'Las contraseñas no coinciden';
        }
        break;
      case 'dni':
        if (!value) return 'El DNI es requerido';
        if (!/^\d{8}$/.test(value.toString())) {
          return 'El DNI debe tener exactamente 8 dígitos numéricos';
        }
        break;
      case 'phoneNumber':
        if (!value) return 'El número de teléfono es requerido';
        if (!/^9\d{8}$/.test(value.toString())) {
          return 'El número debe empezar con 9 y tener 9 dígitos numéricos';
        }
        break;
      case 'age':
        const ageNum = Number(value);
        if (!value || ageNum === 0) return 'La edad es requerida';
        if (ageNum < 1 || ageNum > 120) {
          return 'La edad debe estar entre 1 y 120 años';
        }
        break;
      case 'gender':
        if (!value) return 'El género es requerido';
        break;
      case 'weight':
        const weightNum = Number(value);
        if (!value || weightNum === 0) return 'El peso es requerido';
        if (weightNum < 2) return 'El peso mínimo debe ser 2 kg';
        if (weightNum > 200) return 'El peso máximo debe ser 200 kg';
        break;
      case 'height':
        if (!value || Number(value) === 0) return 'La altura es requerida';
        const heightStr = value.toString();
        if (!/^\d{2,3}$/.test(heightStr)) {
          return 'La altura debe ser un número entero en centímetros (30-220)';
        }
        const heightNum = Number(value);
        if (heightNum < 30 || heightNum > 220) {
          return 'La altura debe estar entre 30 y 220 cm';
        }
        break;
      case 'zone':
        if (!value) return 'La zona es requerida';
        if (!['rural', 'urbana'].includes(value.toString().toLowerCase())) {
          return 'La zona debe ser rural o urbana';
        }
        break;
      case 'occupation':
        if (!value) return 'El nivel educativo es requerido';
        break;
    }
    return '';
  };

  // Función para validar todo el formulario
  const validateAllFields = (): boolean => {
    const newErrors: FormErrors = {};
    const newTouched: { [key: string]: boolean } = {};
    
    // Lista de todos los campos requeridos
    const fieldsToValidate = [
      'fullName', 'email', 'username', 'password', 'confirmPassword',
      'dni', 'phoneNumber', 'age', 'gender', 'weight', 'height', 'zone', 'occupation'
    ];
    
    let isValid = true;
    
    fieldsToValidate.forEach(fieldName => {
      newTouched[fieldName] = true;
      const fieldValue = formData[fieldName as keyof RegistrationFormData];
      const error = validateField(fieldName, fieldValue);
      
      if (error) {
        newErrors[fieldName] = error;
        isValid = false;
      }
    });
    
    setTouched(newTouched);
    setErrors(newErrors);
    
    return isValid;
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    
    if (name === 'dni' || name === 'phoneNumber' || name === 'height') {
      if (!/^\d*$/.test(value)) {
        return;
      }
    }
    
    setFormData(prev => ({ ...prev, [name]: value }));
    setTouched(prev => ({ ...prev, [name]: true }));
    const error = validateField(name, value);
    setErrors(prev => ({ ...prev, [name]: error }));
  };

  const handleBlur = (e: React.FocusEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setTouched(prev => ({ ...prev, [name]: true }));
    const error = validateField(name, value);
    setErrors(prev => ({ ...prev, [name]: error }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validar todos los campos antes de enviar
    const isFormValid = validateAllFields();
    
    if (!isFormValid) {
      alert('Por favor, complete todos los campos requeridos correctamente.');
      return;
    }
    
    setIsSubmitting(true);

    try {
      console.log('Enviando a:', `${API_BASE_URL}/api/register`);
      
      const response = await fetch(`${API_BASE_URL}/api/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData)
      });

      const data = await response.json();

      if (!response.ok) {
        if (data.detail) {
          if (data.detail.includes("usuario")) {
            setErrors(prev => ({ ...prev, username: data.detail }));
          } else if (data.detail.includes("correo")) {
            setErrors(prev => ({ ...prev, email: data.detail }));
          } else if (data.detail.includes("DNI")) {
            setErrors(prev => ({ ...prev, dni: data.detail }));
          } else if (data.detail.includes("teléfono")) {
            setErrors(prev => ({ ...prev, phoneNumber: data.detail }));
          } else {
            alert(data.detail);
          }
        }
        setIsSubmitting(false);
        return;
      }

      setSuccessMessage('¡Usuario registrado exitosamente! Redirigiendo al login...');

    } catch (error) {
      console.error('Error al registrar:', error);
      alert('Error al registrar usuario. Por favor, intente nuevamente.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderError = (fieldName: string) => {
    if (touched[fieldName] && errors[fieldName]) {
      return (
        <div className="mt-1 text-sm text-red-600">
          {errors[fieldName]}
        </div>
      );
    }
    return null;
  };

  return (
    <form onSubmit={handleSubmit} className="max-w-md mx-auto p-6 bg-white rounded-lg shadow-md">
      <h2 className="text-2xl font-bold mb-6">Registro de Usuario</h2>
      {successMessage && (
        <div className="mb-4 p-4 bg-green-100 border border-green-400 text-green-700 rounded">
          {successMessage}
        </div>
      )}

      <div className="space-y-4">
        {/* Sección de Información de Cuenta */}
        <div className="bg-gray-50 p-4 rounded-lg mb-6">
          <h3 className="text-lg font-semibold mb-4">Información de Cuenta</h3>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">
                Nombre Completo <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                name="fullName"
                className="w-full p-2 border rounded focus:ring-2 focus:ring-green-500 focus:border-transparent"
                value={formData.fullName}
                onChange={handleChange}
                onBlur={handleBlur}
                onKeyPress={handleKeyPress}
                required
              />
              {renderError('fullName')}
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">
                Correo Electrónico <span className="text-red-500">*</span>
              </label>
              <input
                type="email"
                name="email"
                className="w-full p-2 border rounded focus:ring-2 focus:ring-green-500 focus:border-transparent"
                value={formData.email}
                onChange={handleChange}
                onBlur={handleBlur}
                required
              />
              {renderError('email')}
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">
                Nombre de Usuario <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                name="username"
                className="w-full p-2 border rounded focus:ring-2 focus:ring-green-500 focus:border-transparent"
                value={formData.username}
                onChange={handleChange}
                onBlur={handleBlur}
                required
              />
              {renderError('username')}
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">
                Contraseña <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  name="password"
                  className="w-full p-2 border rounded focus:ring-2 focus:ring-green-500 focus:border-transparent"
                  value={formData.password}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  required
                />
                <button
                  type="button"
                  className="absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-500 hover:text-gray-700 focus:outline-none"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
                >
                  {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                </button>
              </div>
              {renderError('password')}
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">
                Confirmar Contraseña <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <input
                  type={showConfirmPassword ? "text" : "password"}
                  name="confirmPassword"
                  className="w-full p-2 border rounded focus:ring-2 focus:ring-green-500 focus:border-transparent"
                  value={formData.confirmPassword}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  required
                />
                <button
                  type="button"
                  className="absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-500 hover:text-gray-700 focus:outline-none"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  aria-label={showConfirmPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
                >
                  {showConfirmPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                </button>
              </div>
              {renderError('confirmPassword')}
            </div>
          </div>
        </div>

        {/* Sección de Información Personal */}
        <div className="bg-gray-50 p-4 rounded-lg mb-6">
          <h3 className="text-lg font-semibold mb-4">Información Personal</h3>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">
                DNI <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                name="dni"
                maxLength={8}
                pattern="\d*"
                inputMode="numeric"
                className="w-full p-2 border rounded focus:ring-2 focus:ring-green-500 focus:border-transparent"
                value={formData.dni}
                onChange={handleChange}
                onBlur={handleBlur}
                onKeyPress={handleKeyPress}
                required
              />
              {renderError('dni')}
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">
                Teléfono <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                name="phoneNumber"
                maxLength={9}
                pattern="\d*"
                inputMode="numeric"
                className="w-full p-2 border rounded focus:ring-2 focus:ring-green-500 focus:border-transparent"
                value={formData.phoneNumber}
                onChange={handleChange}
                onBlur={handleBlur}
                onKeyPress={handleKeyPress}
                required
              />
              {renderError('phoneNumber')}
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">
                Edad <span className="text-red-500">*</span>
              </label>
              <input
                type="number"
                name="age"
                min="1"
                max="120"
                className="w-full p-2 border rounded focus:ring-2 focus:ring-green-500 focus:border-transparent"
                value={formData.age || ''}
                onChange={handleChange}
                onBlur={handleBlur}
                required
              />
              {renderError('age')}
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">
                Género <span className="text-red-500">*</span>
              </label>
              <select
                name="gender"
                className="w-full p-2 border rounded focus:ring-2 focus:ring-green-500 focus:border-transparent"
                value={formData.gender}
                onChange={handleChange}
                onBlur={handleBlur}
                required
              >
                <option value="">Seleccionar...</option>
                <option value="masculino">Masculino</option>
                <option value="femenino">Femenino</option>
                <option value="otro">Otro</option>
              </select>
              {renderError('gender')}
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">
                Peso (kg) <span className="text-red-500">*</span>
              </label>
              <input
                type="number"
                name="weight"
                min="2"
                max="200"
                step="0.1"
                className="w-full p-2 border rounded focus:ring-2 focus:ring-green-500 focus:border-transparent"
                value={formData.weight || ''}
                onChange={handleChange}
                onBlur={handleBlur}
                required
              />
              {renderError('weight')}
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">
                Altura (cm) <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                name="height"
                pattern="\d*"
                inputMode="numeric"
                maxLength={3}
                placeholder="Ej: 172"
                className="w-full p-2 border rounded focus:ring-2 focus:ring-green-500 focus:border-transparent"
                value={formData.height || ''}
                onChange={handleChange}
                onBlur={handleBlur}
                onKeyPress={handleKeyPress}
                required
              />
              {renderError('height')}
            </div>
          </div>
        </div>

        {/* Sección de Información Adicional */}
        <div className="bg-gray-50 p-4 rounded-lg mb-6">
          <h3 className="text-lg font-semibold mb-4">Información Adicional</h3>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">
                Zona Donde Vive <span className="text-red-500">*</span>
              </label>
              <select
                name="zone"
                className="w-full p-2 border rounded focus:ring-2 focus:ring-green-500 focus:border-transparent"
                value={formData.zone}
                onChange={handleChange}
                onBlur={handleBlur}
                required
              >
                <option value="">Seleccionar...</option>
                <option value="rural">Rural</option>
                <option value="urbana">Urbana</option>
              </select>
              {renderError('zone')}
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">
                Nivel Educativo <span className="text-red-500">*</span>
              </label>
              <select
                name="occupation"
                className="w-full p-2 border rounded focus:ring-2 focus:ring-green-500 focus:border-transparent"
                value={formData.occupation}
                onChange={handleChange}
                onBlur={handleBlur}
                required
              >
                <option value="">Seleccionar...</option>
                {occupationOptions.map((option, index) => (
                  <option key={index} value={option}>
                    {option}
                  </option>
                ))}
              </select>
              {renderError('occupation')}
            </div>
          </div>
        </div>

        <button
            type="submit"
            disabled={isSubmitting}
            className={`w-full bg-green-600 text-white p-2 rounded hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 ${
                isSubmitting ? 'opacity-50 cursor-not-allowed' : ''
            }`}
        >
            {isSubmitting ? 'Registrando...' : 'Registrarse'}
        </button>
      </div>
    </form>
  );
};

export default RegisterForm;
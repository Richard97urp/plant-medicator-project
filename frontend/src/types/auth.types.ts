export interface LoginCredentials {
    identifier: string;
    password: string;
  }
  
  export interface RegistrationFormData {
    username: string;
    password: string;
    phoneNumber: string;
    dni: string;
    zone: string;
    age: number;
    weight: number;
    height: number;
    gender: string;
    occupation: string;
  }
  
  export interface LoginFormProps {
    onLoginSuccess: () => void;
  }
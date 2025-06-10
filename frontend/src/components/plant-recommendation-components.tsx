import React from 'react';

interface PlantCardProps {
  name: string;
  scientificName: string;
  description: string;
  effectiveness: string;
}

interface PreparationInstructionsProps {
  title: string;
  time: string;
  instructions: string[];
  warning: string;
}

interface PlantSections {
  [key: string]: string;
}

const PlantCard: React.FC<PlantCardProps> = ({ name, scientificName, description, effectiveness }) => (
  <div className="bg-green-50 rounded-lg p-4 mb-4 border border-green-100">
    <div className="flex items-start gap-2">
      <span className="text-green-600">🌿</span>
      <div className="flex-1">
        <h3 className="font-bold text-lg">
          {name} <span className="italic font-normal text-gray-600">({scientificName})</span>
        </h3>
        <p className="text-gray-700 mt-1">{description}</p>
        <div className="mt-2">
          <span className="text-sm">
            ⭐ Efectividad: {effectiveness}
          </span>
        </div>
      </div>
    </div>
  </div>
);

const PreparationInstructions: React.FC<PreparationInstructionsProps> = ({ title, time, instructions, warning }) => (
  <div className="bg-white rounded-lg p-4 border border-gray-200">
    <div className="flex items-center gap-2 mb-4">
      <span className="text-green-600">⚗️</span>
      <h3 className="font-bold text-lg">{title}</h3>
    </div>
    
    <div className="flex items-center gap-2 mb-4">
      <span className="text-gray-500">⏱</span>
      <p>Tiempo de preparación: {time}</p>
    </div>

    <div className="mb-4">
      <h4 className="font-semibold mb-2">Instrucciones:</h4>
      <ol className="list-decimal pl-5 space-y-2">
        {instructions.map((instruction, index) => (
          <li key={index} className="text-gray-700">{instruction}</li>
        ))}
      </ol>
    </div>

    {warning && (
      <div className="bg-yellow-50 p-3 rounded-lg mt-4">
        <div className="flex items-start gap-2">
          <span className="text-yellow-600">⚠️</span>
          <p className="text-sm text-gray-700">{warning}</p>
        </div>
      </div>
    )}
  </div>
);

const formatPlantRecommendation = (response: string): JSX.Element => {
  const plants = response.split('\n')
    .filter((line: string) => line.startsWith('PLANTA_'))
    .map((plant: string) => {
      const [name, description, effectiveness] = plant.split('|').map((s: string) => s.trim());
      const matches = name.split(':')[1].trim().match(/([^(]+)\s*\(([^)]+)\)/);
      
      if (!matches) {
        return {
          name: 'Nombre no disponible',
          scientificName: 'No disponible',
          description: description || '',
          effectiveness: effectiveness?.split(':')[1]?.trim() || 'No especificada'
        };
      }

      const [, commonName, scientificName] = matches;
      
      return {
        name: commonName.trim(),
        scientificName: scientificName.trim(),
        description: description || '',
        effectiveness: effectiveness?.split(':')[1]?.trim() || 'No especificada'
      };
    });

  return (
    <div className="space-y-4">
      {plants.map((plant, index) => (
        <PlantCard key={index} {...plant} />
      ))}
      <p className="mt-4 text-gray-700">
        Por favor, indícame cuál de estas plantas prefieres para poder darte una recomendación específica de preparación y uso.
      </p>
    </div>
  );
};

const formatPlantPreparation = (response: string): JSX.Element => {
  const sections = response.split('\n')
    .filter((line: string) => line.trim())
    .reduce((acc: PlantSections, line: string) => {
      const [key, value] = line.split(':').map((s: string) => s.trim());
      if (key && value) {
        acc[key] = value;
      }
      return acc;
    }, {});

  const instructions = sections['6. Preparación']?.split('.')
    .filter((s: string) => s.trim())
    .map((s: string) => s.trim()) || [];

  return (
    <PreparationInstructions
      title={`Preparación de ${sections['1. Planta medicinal']?.split('(')[0]?.trim() || 'la planta'}`}
      time="15-20 minutos"
      instructions={instructions}
      warning="Recuerda que esta es una recomendación general. Consulta con un profesional de la salud antes de comenzar cualquier tratamiento con plantas medicinales."
    />
  );
};

export { formatPlantRecommendation, formatPlantPreparation };